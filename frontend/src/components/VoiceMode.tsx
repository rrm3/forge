/**
 * Voice Mode - OpenAI Realtime API integration.
 *
 * Key behaviors:
 * - Mic is muted while AI is speaking (prevents echo/feedback)
 * - Audio playback is queued sequentially (not simultaneous)
 * - Transcript streams word-by-word synced with audio
 * - Pause button mutes mic without disconnecting
 * - Tool calls relay through backend for server-side execution
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { MicOff, Square, Type, Pause, Play } from 'lucide-react';
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
  const [streamingAssistantText, setStreamingAssistantText] = useState('');
  const [paused, setPaused] = useState(false);

  // Refs
  const openaiWsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const animFrameRef = useRef<number>(0);
  const playbackNextTime = useRef(0);
  const playbackCtxRef = useRef<AudioContext | null>(null);

  // Mic mute flag - true while AI is speaking to prevent echo pickup
  const micMutedRef = useRef(false);
  const pausedRef = useRef(false);

  useEffect(() => { pausedRef.current = paused; }, [paused]);
  useEffect(() => { onTranscriptUpdate?.(transcript); }, [transcript, onTranscriptUpdate]);

  // ---- Connection lifecycle ----

  useEffect(() => {
    let cancelled = false;

    const unsubMessage = forgeWs.onMessage((msg: ServerMessage) => {
      if (cancelled) return;
      if (msg.type === 'voice_token' && 'session_id' in msg && msg.session_id === sessionId) {
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

  // Audio level visualization
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

  // ---- OpenAI connection ----

  function connectToOpenAI(token: string) {
    if (openaiWsRef.current && openaiWsRef.current.readyState < WebSocket.CLOSING) return;

    setupMicrophone().then((ok) => {
      if (!ok) return;

      const ws = new WebSocket(
        'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17',
        ['realtime', `openai-insecure-api-key.${token}`, 'openai-beta.realtime-v1'],
      );
      openaiWsRef.current = ws;

      ws.onopen = () => {
        setConnecting(false);
        setOrbState('idle');
        startAudioCapture(ws);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'session.created') {
            // Session ready - trigger initial greeting
            ws.send(JSON.stringify({ type: 'response.create' }));
          }
          handleOpenAIEvent(data);
        } catch {}
      };

      ws.onclose = (e) => {
        if (e.code !== 1000) setOrbState('reconnecting');
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

    const processor = ctx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      if (ws.readyState !== WebSocket.OPEN) return;
      // Don't send audio while AI is speaking (prevents echo) or while paused
      if (micMutedRef.current || pausedRef.current) return;

      const input = e.inputBuffer.getChannelData(0);
      const pcm16 = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      const bytes = new Uint8Array(pcm16.buffer);
      let binary = '';
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);

      ws.send(JSON.stringify({ type: 'input_audio_buffer.append', audio: btoa(binary) }));
    };

    analyser.connect(processor);
    processor.connect(ctx.destination);
  }

  // ---- OpenAI event handling ----

  function handleOpenAIEvent(data: { type: string; [key: string]: unknown }) {
    switch (data.type) {
      case 'input_audio_buffer.speech_started':
        setOrbState('listening');
        break;

      case 'input_audio_buffer.speech_stopped':
        setOrbState('idle');
        break;

      case 'response.audio.delta':
        setOrbState('speaking');
        micMutedRef.current = true; // Mute mic while AI speaks
        queueAudioChunk((data as { delta?: string }).delta || '');
        break;

      case 'response.audio.done':
        // Unmute mic after a short delay (let audio finish playing)
        setTimeout(() => { micMutedRef.current = false; }, 500);
        setOrbState('listening');
        break;

      case 'response.audio_transcript.delta': {
        const delta = ((data as { delta?: string }).delta || '');
        if (delta) setStreamingAssistantText(prev => prev + delta);
        break;
      }

      case 'conversation.item.input_audio_transcription.completed': {
        const text = ((data as { transcript?: string }).transcript || '').trim();
        if (text) {
          setTranscript(prev => {
            if (prev.length > 0 && prev[prev.length - 1].role === 'user') {
              return [...prev.slice(0, -1), { role: 'user', text }];
            }
            return [...prev, { role: 'user', text }];
          });
          forgeWs.send({ action: 'transcript', session_id: sessionId, role: 'user', content: text });
        }
        break;
      }

      case 'response.audio_transcript.done': {
        const text = ((data as { transcript?: string }).transcript || '').trim();
        setStreamingAssistantText('');
        if (text) {
          setTranscript(prev => [...prev, { role: 'assistant', text }]);
          forgeWs.send({ action: 'transcript', session_id: sessionId, role: 'assistant', content: text });
        }
        break;
      }

      case 'response.function_call_arguments.done': {
        setOrbState('tool_call');
        micMutedRef.current = true;
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
        // Don't show transient errors to user, just log
        if (!msg.includes('active response in progress')) {
          setError(msg);
        }
        break;
      }
    }
  }

  // ---- Sequential audio playback ----

  function queueAudioChunk(base64Audio: string) {
    const ctx = playbackCtxRef.current;
    if (!ctx || !base64Audio) return;

    try {
      const binary = atob(base64Audio);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const pcm16 = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) float32[i] = pcm16[i] / 0x8000;

      const buffer = ctx.createBuffer(1, float32.length, SAMPLE_RATE);
      buffer.getChannelData(0).set(float32);

      const now = ctx.currentTime;
      const startTime = Math.max(now, playbackNextTime.current);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      source.start(startTime);
      playbackNextTime.current = startTime + buffer.duration;
    } catch {}
  }

  function relayToolResult(callId: string, result: string) {
    const ws = openaiWsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({
      type: 'conversation.item.create',
      item: { type: 'function_call_output', call_id: callId, output: result },
    }));
    ws.send(JSON.stringify({ type: 'response.create' }));
    // Unmute after tool result so AI can respond
    setTimeout(() => { micMutedRef.current = false; }, 200);
  }

  // ---- Pause/resume ----

  function togglePause() {
    setPaused(p => !p);
  }

  // ---- Cleanup ----

  function cleanup() {
    if (processorRef.current) { processorRef.current.disconnect(); processorRef.current = null; }
    if (openaiWsRef.current) { openaiWsRef.current.close(); openaiWsRef.current = null; }
    if (mediaStreamRef.current) { mediaStreamRef.current.getTracks().forEach(t => t.stop()); mediaStreamRef.current = null; }
    if (audioContextRef.current) { audioContextRef.current.close(); audioContextRef.current = null; }
    if (playbackCtxRef.current) { playbackCtxRef.current.close(); playbackCtxRef.current = null; }
    analyserRef.current = null;
    playbackNextTime.current = 0;
    micMutedRef.current = false;
  }

  // ---- Render ----

  if (micDenied) {
    return (
      <div className="flex flex-col items-center justify-center h-full px-6 text-center">
        <MicOff className="w-12 h-12 mb-4" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
        <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>Microphone access needed</h3>
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
      {/* Orb */}
      <div className="flex-shrink-0 flex items-center justify-center pt-8 pb-4">
        {connecting ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--color-primary)' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>Connecting voice...</span>
          </div>
        ) : (
          <VoiceOrb state={paused ? 'idle' : orbState} audioLevel={paused ? 0 : audioLevel} size={120} />
        )}
      </div>

      {/* Status */}
      <div className="text-center mb-4" aria-live="polite">
        {error ? (
          <div>
            <p className="text-sm font-medium mb-2" style={{ color: 'var(--color-error)' }}>{error}</p>
            <button onClick={() => { setError(null); setConnecting(true); forgeWs.requestVoiceSession(sessionId, sessionType); }}
              className="text-sm font-semibold" style={{ color: 'var(--color-primary)' }}>Try again</button>
          </div>
        ) : (
          <p className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
            {paused ? 'Paused - tap resume when ready' :
             orbState === 'listening' ? 'Listening...' :
             orbState === 'speaking' ? 'AI is speaking...' :
             orbState === 'tool_call' ? 'Looking something up...' :
             orbState === 'reconnecting' ? 'Reconnecting...' : 'Ready'}
          </p>
        )}
      </div>

      {/* Transcript */}
      <div className="flex-1 overflow-y-auto w-full max-w-2xl px-4">
        {transcript.map((entry, i) => (
          <div key={i} className={`mb-3 ${entry.role === 'user' ? 'text-right' : 'text-left'}`}>
            <span className={`inline-block px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${entry.role === 'user' ? 'bg-[var(--color-user-bubble)]' : ''}`}
              style={{ color: 'var(--color-text-primary)', maxWidth: '80%', display: 'inline-block' }}>
              {entry.text}
            </span>
          </div>
        ))}
        {streamingAssistantText && (
          <div className="mb-3 text-left">
            <span className="inline-block px-4 py-2.5 rounded-2xl text-sm leading-relaxed"
              style={{ color: 'var(--color-text-primary)', maxWidth: '80%', display: 'inline-block' }}>
              {streamingAssistantText}
            </span>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-3 pb-6 pt-3">
        <button onClick={onExit}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold border"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
          <Type className="w-4 h-4" strokeWidth={1.5} /> Text
        </button>
        <button onClick={togglePause}
          className="flex items-center justify-center w-12 h-12 rounded-full border-2 transition-colors"
          style={{
            borderColor: paused ? 'var(--color-primary)' : 'var(--color-border)',
            backgroundColor: paused ? 'var(--color-primary-subtle)' : 'var(--color-surface-white)',
            color: paused ? 'var(--color-primary)' : 'var(--color-text-muted)',
          }}
          title={paused ? 'Resume' : 'Pause'}
          aria-label={paused ? 'Resume voice' : 'Pause voice'}>
          {paused ? <Play className="w-5 h-5" strokeWidth={1.5} /> : <Pause className="w-5 h-5" strokeWidth={1.5} />}
        </button>
        <button onClick={() => { cleanup(); onExit(); }}
          className="flex items-center justify-center w-12 h-12 rounded-full text-white"
          style={{ backgroundColor: 'var(--color-error)' }}
          aria-label="Stop voice session">
          <Square className="w-5 h-5" fill="currentColor" strokeWidth={0} />
        </button>
      </div>
    </div>
  );
}
