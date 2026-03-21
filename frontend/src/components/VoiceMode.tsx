/**
 * Voice Mode - OpenAI Realtime API integration.
 *
 * Connects to OpenAI's Realtime API using an ephemeral token from the backend.
 * Sends microphone audio as base64 PCM16 frames. Receives and plays audio responses.
 * Relays tool calls to the backend for server-side execution.
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

// PCM16 audio config matching OpenAI Realtime API requirements
const SAMPLE_RATE = 24000;

export function VoiceMode({ sessionId, sessionType, onExit, transcript: externalTranscript, onTranscriptUpdate }: VoiceModeProps) {
  const [orbState, setOrbState] = useState<OrbState>('idle');
  const [audioLevel, setAudioLevel] = useState(0);
  const [transcript, setTranscript] = useState<{ role: string; text: string }[]>(externalTranscript || []);
  const [error, setError] = useState<string | null>(null);
  const [micDenied, setMicDenied] = useState(false);
  const [connecting, setConnecting] = useState(true);

  const rtcRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const animFrameRef = useRef<number>(0);
  const transcriptRef = useRef(transcript);

  useEffect(() => { transcriptRef.current = transcript; }, [transcript]);

  // Notify parent of transcript changes
  useEffect(() => {
    onTranscriptUpdate?.(transcript);
  }, [transcript, onTranscriptUpdate]);

  // Request ephemeral token and connect
  useEffect(() => {
    let cancelled = false;

    const unsubMessage = forgeWs.onMessage((msg: ServerMessage) => {
      if (msg.type === 'voice_token' && 'session_id' in msg && msg.session_id === sessionId) {
        if (!cancelled && !rtcRef.current) {
          connectToRealtime(msg.token);
        }
      }
      if (msg.type === 'tool_result' && 'session_id' in msg && msg.session_id === sessionId) {
        if (rtcRef.current?.readyState === WebSocket.OPEN) {
          rtcRef.current.send(JSON.stringify({
            type: 'conversation.item.create',
            item: {
              type: 'function_call_output',
              call_id: (msg as { tool_call_id: string }).tool_call_id,
              output: (msg as { result: string }).result,
            },
          }));
          rtcRef.current.send(JSON.stringify({ type: 'response.create' }));
        }
      }
    });

    forgeWs.requestVoiceSession(sessionId, sessionType);

    return () => {
      cancelled = true;
      unsubMessage();
      // Clean up any connection from this effect instance
      disconnectRealtime();
    };
  }, [sessionId, sessionType]);

  // Audio level animation loop
  useEffect(() => {
    function updateLevel() {
      if (analyserRef.current) {
        const data = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(data);
        const avg = data.reduce((sum, v) => sum + v, 0) / data.length;
        setAudioLevel(Math.min(avg / 128, 1));
      }
      animFrameRef.current = requestAnimationFrame(updateLevel);
    }
    updateLevel();
    return () => cancelAnimationFrame(animFrameRef.current);
  }, []);

  const connectToRealtime = useCallback(async (token: string) => {
    try {
      // Request microphone
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: SAMPLE_RATE,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
          },
        });
      } catch {
        setMicDenied(true);
        setConnecting(false);
        return;
      }
      mediaStreamRef.current = stream;

      // Audio context for capture and analysis
      const audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
      audioContextRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);

      // Analyser for visualization
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Playback context for AI audio
      playbackCtxRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });

      // Connect to OpenAI Realtime API with ephemeral token
      // OpenAI accepts the token via subprotocol headers
      const ws = new WebSocket(
        `wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17`,
        [
          'realtime',
          `openai-insecure-api-key.${token}`,
          'openai-beta.realtime-v1',
        ],
      );

      ws.onopen = () => {
        setConnecting(false);
        setOrbState('listening');

        // Start capturing and sending audio
        startAudioCapture(audioCtx, source, ws);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleRealtimeEvent(data);
        } catch { /* ignore */ }
      };

      ws.onclose = (e) => {
        console.log('Realtime WS closed:', e.code, e.reason);
        if (e.code !== 1000) {
          setOrbState('reconnecting');
        }
      };

      ws.onerror = (e) => {
        console.error('Realtime WS error:', e);
        setError('Voice connection failed. The OpenAI Realtime API may not be available.');
        setConnecting(false);
      };

      rtcRef.current = ws;
    } catch (err) {
      console.error('Voice setup failed:', err);
      setError(`Voice setup failed: ${err}`);
      setConnecting(false);
    }
  }, [sessionId]);

  function startAudioCapture(audioCtx: AudioContext, source: MediaStreamAudioSourceNode, ws: WebSocket) {
    // Use ScriptProcessorNode to capture raw PCM audio
    // Buffer size of 4096 at 24kHz = ~170ms chunks
    const processor = audioCtx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      if (ws.readyState !== WebSocket.OPEN) return;

      const inputData = e.inputBuffer.getChannelData(0);
      // Convert float32 to PCM16
      const pcm16 = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        const s = Math.max(-1, Math.min(1, inputData[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }

      // Convert to base64
      const bytes = new Uint8Array(pcm16.buffer);
      let binary = '';
      for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      const base64 = btoa(binary);

      // Send audio append event
      ws.send(JSON.stringify({
        type: 'input_audio_buffer.append',
        audio: base64,
      }));
    };

    source.connect(processor);
    processor.connect(audioCtx.destination); // Required for ScriptProcessor to work
  }

  const handleRealtimeEvent = useCallback((data: { type: string; [key: string]: unknown }) => {
    switch (data.type) {
      case 'session.created':
        console.log('Realtime session created');
        break;

      case 'input_audio_buffer.speech_started':
        setOrbState('listening');
        break;

      case 'input_audio_buffer.speech_stopped':
        setOrbState('idle');
        break;

      case 'response.audio.delta': {
        setOrbState('speaking');
        // Play audio response
        const audioData = (data as { delta?: string }).delta;
        if (audioData && playbackCtxRef.current) {
          playAudioChunk(audioData, playbackCtxRef.current);
        }
        break;
      }

      case 'response.audio.done':
        setOrbState('listening');
        break;

      case 'conversation.item.input_audio_transcription.completed': {
        const text = (data as { transcript?: string }).transcript || '';
        if (text.trim()) {
          setTranscript(prev => [...prev, { role: 'user', text: text.trim() }]);
          forgeWs.send({
            action: 'transcript',
            session_id: sessionId,
            role: 'user',
            content: text.trim(),
          });
        }
        break;
      }

      case 'response.audio_transcript.done': {
        const text = (data as { transcript?: string }).transcript || '';
        if (text.trim()) {
          setTranscript(prev => [...prev, { role: 'assistant', text: text.trim() }]);
          forgeWs.send({
            action: 'transcript',
            session_id: sessionId,
            role: 'assistant',
            content: text.trim(),
          });
        }
        break;
      }

      case 'response.function_call_arguments.done': {
        const callId = (data as { call_id?: string }).call_id || '';
        const name = (data as { name?: string }).name || '';
        const args = (data as { arguments?: string }).arguments || '{}';
        setOrbState('tool_call');

        forgeWs.send({
          action: 'tool_call',
          session_id: sessionId,
          tool: name,
          tool_call_id: callId,
          args: JSON.parse(args),
        });
        break;
      }

      case 'error': {
        const msg = (data as { error?: { message?: string } }).error?.message || 'Voice error';
        console.error('Realtime error:', msg);
        setError(msg);
        break;
      }
    }
  }, [sessionId]);

  function disconnectRealtime() {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (rtcRef.current) {
      rtcRef.current.close();
      rtcRef.current = null;
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
  }

  function handleStop() {
    disconnectRealtime();
    onExit();
  }

  function handleRetry() {
    setError(null);
    setMicDenied(false);
    setConnecting(true);
    forgeWs.requestVoiceSession(sessionId, sessionType);
  }

  if (micDenied) {
    return (
      <div className="flex flex-col items-center justify-center h-full px-6 text-center">
        <MicOff className="w-12 h-12 mb-4" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
        <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
          Microphone access needed
        </h3>
        <p className="text-sm mb-4 max-w-sm" style={{ color: 'var(--color-text-muted)' }}>
          To use voice mode, allow microphone access in your browser settings, then try again.
        </p>
        <div className="flex gap-3">
          <button
            onClick={handleRetry}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-white"
            style={{ backgroundColor: 'var(--color-primary)' }}
          >
            Try Again
          </button>
          <button
            onClick={onExit}
            className="px-4 py-2 rounded-lg text-sm font-semibold border"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
          >
            Use Text Instead
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
      {/* Voice orb area */}
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

      {/* Status text */}
      <div className="text-center mb-4" aria-live="polite">
        {error ? (
          <div>
            <p className="text-sm font-medium mb-2" style={{ color: 'var(--color-error)' }}>{error}</p>
            <button onClick={handleRetry} className="text-sm font-semibold" style={{ color: 'var(--color-primary)' }}>
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
          <div
            key={i}
            className={`mb-3 ${entry.role === 'user' ? 'text-right' : 'text-left'}`}
          >
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

      {/* Bottom controls */}
      <div className="flex items-center justify-center gap-4 pb-6 pt-3">
        <button
          onClick={onExit}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold border transition-colors"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
          title="Switch to text"
        >
          <Type className="w-4 h-4" strokeWidth={1.5} />
          Text
        </button>
        <button
          onClick={handleStop}
          className="flex items-center justify-center w-12 h-12 rounded-full text-white transition-colors"
          style={{ backgroundColor: 'var(--color-error)' }}
          title="Stop voice"
          aria-label="Stop voice session"
        >
          <Square className="w-5 h-5" fill="currentColor" strokeWidth={0} />
        </button>
      </div>
    </div>
  );
}

// Play a base64-encoded PCM16 audio chunk
function playAudioChunk(base64Audio: string, audioCtx: AudioContext) {
  try {
    const binary = atob(base64Audio);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    const pcm16 = new Int16Array(bytes.buffer);

    // Convert PCM16 to float32
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
      float32[i] = pcm16[i] / 0x8000;
    }

    const buffer = audioCtx.createBuffer(1, float32.length, SAMPLE_RATE);
    buffer.getChannelData(0).set(float32);

    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);
    source.start();
  } catch {
    // Ignore audio playback errors
  }
}
