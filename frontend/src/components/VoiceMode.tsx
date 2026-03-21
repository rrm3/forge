/**
 * Voice Mode - OpenAI Realtime API integration.
 *
 * Architecture:
 * 1. Backend creates an OpenAI Realtime session with system prompt + tools
 * 2. Backend returns an ephemeral token
 * 3. Frontend connects to OpenAI's WebSocket with the token
 * 4. Microphone audio is captured, converted to PCM16, sent as base64 frames
 * 5. AI audio responses are queued and played back sequentially
 * 6. Tool calls are relayed to the backend for execution
 * 7. Transcripts are persisted to the backend for session continuity
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { MicOff, Square, Type } from 'lucide-react';
import { VoiceOrb, type OrbState } from './VoiceOrb';
import { forgeWs } from '../api/websocket';
import type { ServerMessage } from '../api/websocket';

interface VoiceModeProps {
  sessionId: string;
  sessionType?: string;
  onExit: () => void;
  transcript?: { role: string; text: string }[];
  onTranscriptUpdate?: (entries: { role: string; text: string }[]) => void;
}

const SAMPLE_RATE = 24000;

export function VoiceMode({ sessionId, sessionType, onExit, transcript: externalTranscript, onTranscriptUpdate }: VoiceModeProps) {
  const [orbState, setOrbState] = useState<OrbState>('idle');
  const [audioLevel, setAudioLevel] = useState(0);
  const [transcript, setTranscript] = useState<{ role: string; text: string }[]>(externalTranscript || []);
  const [error, setError] = useState<string | null>(null);
  const [micDenied, setMicDenied] = useState(false);
  const [connecting, setConnecting] = useState(true);

  // Refs for audio/WebSocket resources
  const openaiWsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const animFrameRef = useRef<number>(0);

  // Audio playback queue - plays chunks sequentially, not simultaneously
  const playbackNextTime = useRef(0);
  const playbackCtxRef = useRef<AudioContext | null>(null);

  // Notify parent of transcript changes
  useEffect(() => {
    onTranscriptUpdate?.(transcript);
  }, [transcript, onTranscriptUpdate]);

  // ---- Core connection lifecycle ----

  useEffect(() => {
    let cancelled = false;

    const unsubMessage = forgeWs.onMessage((msg: ServerMessage) => {
      if (cancelled) return;

      if (msg.type === 'voice_token' && 'session_id' in msg && msg.session_id === sessionId) {
        // Only connect if we don't already have a connection
        if (!openaiWsRef.current || openaiWsRef.current.readyState >= WebSocket.CLOSING) {
          connectToOpenAI(msg.token);
        }
      }

      if (msg.type === 'tool_result' && 'session_id' in msg && msg.session_id === sessionId) {
        relayToolResult(
          (msg as { tool_call_id: string }).tool_call_id,
          (msg as { result: string }).result,
        );
      }
    });

    forgeWs.requestVoiceSession(sessionId, sessionType);

    return () => {
      cancelled = true;
      unsubMessage();
      cleanup();
    };
  }, [sessionId, sessionType]);

  // Audio level visualization loop
  useEffect(() => {
    function tick() {
      if (analyserRef.current) {
        const data = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(data);
        const avg = data.reduce((sum, v) => sum + v, 0) / data.length;
        setAudioLevel(Math.min(avg / 128, 1));
      }
      animFrameRef.current = requestAnimationFrame(tick);
    }
    animFrameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, []);

  // ---- OpenAI Realtime connection ----

  function connectToOpenAI(token: string) {
    // Ensure no existing connection
    if (openaiWsRef.current && openaiWsRef.current.readyState < WebSocket.CLOSING) {
      return;
    }

    setupMicrophone().then((micReady) => {
      if (!micReady) return;

      const ws = new WebSocket(
        'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17',
        ['realtime', `openai-insecure-api-key.${token}`, 'openai-beta.realtime-v1'],
      );
      openaiWsRef.current = ws;

      ws.onopen = () => {
        setConnecting(false);
        setOrbState('listening');
        startAudioCapture(ws);

        // Tell OpenAI to generate the initial greeting
        ws.send(JSON.stringify({ type: 'response.create' }));
      };

      ws.onmessage = (event) => {
        try {
          handleOpenAIEvent(JSON.parse(event.data));
        } catch { /* ignore parse errors */ }
      };

      ws.onclose = (e) => {
        console.log('OpenAI WS closed:', e.code, e.reason);
        if (e.code !== 1000) {
          setOrbState('reconnecting');
        }
      };

      ws.onerror = () => {
        setError('Voice connection failed.');
        setConnecting(false);
      };
    });
  }

  async function setupMicrophone(): Promise<boolean> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: SAMPLE_RATE, channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      mediaStreamRef.current = stream;

      const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
      audioContextRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Playback context for AI audio
      playbackCtxRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });
      playbackNextTime.current = 0;

      return true;
    } catch {
      setMicDenied(true);
      setConnecting(false);
      return false;
    }
  }

  function startAudioCapture(ws: WebSocket) {
    const ctx = audioContextRef.current;
    const analyser = analyserRef.current;
    if (!ctx || !analyser) return;

    // ScriptProcessorNode captures raw PCM for sending to OpenAI
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      if (ws.readyState !== WebSocket.OPEN) return;
      const input = e.inputBuffer.getChannelData(0);

      // Float32 -> PCM16 -> base64
      const pcm16 = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      const bytes = new Uint8Array(pcm16.buffer);
      let binary = '';
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);

      ws.send(JSON.stringify({
        type: 'input_audio_buffer.append',
        audio: btoa(binary),
      }));
    };

    // Connect through analyser so both visualization and capture work
    analyser.connect(processor);
    processor.connect(ctx.destination);
  }

  // ---- Handle OpenAI Realtime events ----

  function handleOpenAIEvent(data: { type: string; [key: string]: unknown }) {
    switch (data.type) {
      case 'session.created':
        console.log('OpenAI Realtime session created');
        break;

      case 'input_audio_buffer.speech_started':
        setOrbState('listening');
        break;

      case 'input_audio_buffer.speech_stopped':
        setOrbState('idle');
        break;

      case 'response.audio.delta':
        setOrbState('speaking');
        queueAudioChunk((data as { delta?: string }).delta || '');
        break;

      case 'response.audio.done':
        setOrbState('listening');
        break;

      case 'conversation.item.input_audio_transcription.completed': {
        const text = ((data as { transcript?: string }).transcript || '').trim();
        if (text) {
          setTranscript(prev => [...prev, { role: 'user', text }]);
          forgeWs.send({ action: 'transcript', session_id: sessionId, role: 'user', content: text });
        }
        break;
      }

      case 'response.audio_transcript.done': {
        const text = ((data as { transcript?: string }).transcript || '').trim();
        if (text) {
          setTranscript(prev => [...prev, { role: 'assistant', text }]);
          forgeWs.send({ action: 'transcript', session_id: sessionId, role: 'assistant', content: text });
        }
        break;
      }

      case 'response.function_call_arguments.done': {
        setOrbState('tool_call');
        const callId = (data as { call_id?: string }).call_id || '';
        const name = (data as { name?: string }).name || '';
        const args = (data as { arguments?: string }).arguments || '{}';
        forgeWs.send({
          action: 'tool_call', session_id: sessionId,
          tool: name, tool_call_id: callId, args: JSON.parse(args),
        });
        break;
      }

      case 'error': {
        const msg = (data as { error?: { message?: string } }).error?.message || 'Voice error';
        console.error('OpenAI Realtime error:', msg);
        setError(msg);
        break;
      }
    }
  }

  // ---- Sequential audio playback queue ----
  // Each audio.delta chunk is scheduled to play AFTER the previous one finishes,
  // preventing the garbled simultaneous playback.

  function queueAudioChunk(base64Audio: string) {
    const ctx = playbackCtxRef.current;
    if (!ctx || !base64Audio) return;

    try {
      // Decode base64 -> PCM16 -> Float32
      const binary = atob(base64Audio);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const pcm16 = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) float32[i] = pcm16[i] / 0x8000;

      // Create audio buffer
      const buffer = ctx.createBuffer(1, float32.length, SAMPLE_RATE);
      buffer.getChannelData(0).set(float32);

      // Schedule playback sequentially
      const now = ctx.currentTime;
      const startTime = Math.max(now, playbackNextTime.current);

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      source.start(startTime);

      // Next chunk starts after this one ends
      playbackNextTime.current = startTime + buffer.duration;
    } catch {
      // Ignore individual chunk playback errors
    }
  }

  // ---- Relay tool results back to OpenAI ----

  function relayToolResult(callId: string, result: string) {
    const ws = openaiWsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    ws.send(JSON.stringify({
      type: 'conversation.item.create',
      item: { type: 'function_call_output', call_id: callId, output: result },
    }));
    ws.send(JSON.stringify({ type: 'response.create' }));
  }

  // ---- Cleanup ----

  function cleanup() {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (openaiWsRef.current) {
      openaiWsRef.current.close();
      openaiWsRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => t.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (playbackCtxRef.current) {
      playbackCtxRef.current.close();
      playbackCtxRef.current = null;
    }
    analyserRef.current = null;
    playbackNextTime.current = 0;
  }

  // ---- UI ----

  if (micDenied) {
    return (
      <div className="flex flex-col items-center justify-center h-full px-6 text-center">
        <MicOff className="w-12 h-12 mb-4" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
        <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
          Microphone access needed
        </h3>
        <p className="text-sm mb-4 max-w-sm" style={{ color: 'var(--color-text-muted)' }}>
          Allow microphone access in your browser settings, then try again.
        </p>
        <div className="flex gap-3">
          <button onClick={() => { setMicDenied(false); setConnecting(true); forgeWs.requestVoiceSession(sessionId, sessionType); }}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-white" style={{ backgroundColor: 'var(--color-primary)' }}>
            Try Again
          </button>
          <button onClick={onExit}
            className="px-4 py-2 rounded-lg text-sm font-semibold border" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
            Use Text Instead
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
      <div className="flex-shrink-0 flex items-center justify-center pt-8 pb-4">
        {connecting ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--color-primary)' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>Connecting voice...</span>
          </div>
        ) : (
          <VoiceOrb state={orbState} audioLevel={audioLevel} />
        )}
      </div>

      <div className="text-center mb-4" aria-live="polite">
        {error ? (
          <div>
            <p className="text-sm font-medium mb-2" style={{ color: 'var(--color-error)' }}>{error}</p>
            <button onClick={() => { setError(null); setConnecting(true); forgeWs.requestVoiceSession(sessionId, sessionType); }}
              className="text-sm font-semibold" style={{ color: 'var(--color-primary)' }}>
              Try again
            </button>
          </div>
        ) : (
          <p className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
            {orbState === 'listening' && 'Listening...'}
            {orbState === 'speaking' && 'AI is speaking...'}
            {orbState === 'tool_call' && 'Looking something up...'}
            {orbState === 'idle' && 'Ready'}
            {orbState === 'reconnecting' && 'Reconnecting...'}
          </p>
        )}
      </div>

      {/* Live transcript */}
      <div className="flex-1 overflow-y-auto w-full max-w-2xl px-4">
        {transcript.map((entry, i) => (
          <div key={i} className={`mb-3 ${entry.role === 'user' ? 'text-right' : 'text-left'}`}>
            <span
              className={`inline-block px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                entry.role === 'user' ? 'bg-[var(--color-user-bubble)]' : ''
              }`}
              style={{ color: 'var(--color-text-primary)', maxWidth: '80%', display: 'inline-block' }}
            >
              {entry.text}
            </span>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-center gap-4 pb-6 pt-3">
        <button onClick={onExit}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold border transition-colors"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
          <Type className="w-4 h-4" strokeWidth={1.5} /> Text
        </button>
        <button onClick={() => { cleanup(); onExit(); }}
          className="flex items-center justify-center w-12 h-12 rounded-full text-white transition-colors"
          style={{ backgroundColor: 'var(--color-error)' }}
          aria-label="Stop voice session">
          <Square className="w-5 h-5" fill="currentColor" strokeWidth={0} />
        </button>
      </div>
    </div>
  );
}
