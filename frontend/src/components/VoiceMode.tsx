/**
 * Voice Mode - OpenAI Realtime API integration.
 *
 * Manages the WebRTC/WebSocket connection to OpenAI, handles audio I/O,
 * relays tool calls to the backend, and persists transcripts.
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
}

export function VoiceMode({ sessionId, sessionType, onExit }: VoiceModeProps) {
  const [orbState, setOrbState] = useState<OrbState>('idle');
  const [audioLevel, setAudioLevel] = useState(0);
  const [transcript, setTranscript] = useState<{ role: string; text: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [micDenied, setMicDenied] = useState(false);
  const [connecting, setConnecting] = useState(true);

  const rtcRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);

  // Request ephemeral token and connect to OpenAI
  useEffect(() => {
    let cancelled = false;

    const unsubMessage = forgeWs.onMessage((msg: ServerMessage) => {
      if (msg.type === 'voice_token' && 'session_id' in msg && msg.session_id === sessionId) {
        if (!cancelled) {
          connectToRealtime(msg.token);
        }
      }
      if (msg.type === 'tool_result' && 'session_id' in msg && msg.session_id === sessionId) {
        // Relay tool result back to OpenAI
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

    // Request the token
    forgeWs.requestVoiceSession(sessionId, sessionType);

    return () => {
      cancelled = true;
      unsubMessage();
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
      // Request microphone access
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch {
        setMicDenied(true);
        setConnecting(false);
        return;
      }

      // Set up audio analysis
      const audioCtx = new AudioContext();
      audioContextRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Connect to OpenAI Realtime
      const ws = new WebSocket(
        `wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17`,
        ['realtime', `openai-insecure-api-key.${token}`, 'openai-beta.realtime-v1'],
      );

      ws.onopen = () => {
        setConnecting(false);
        setOrbState('listening');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleRealtimeEvent(data);
        } catch { /* ignore */ }
      };

      ws.onclose = () => {
        setOrbState('reconnecting');
      };

      ws.onerror = () => {
        setError('Voice connection failed. Try again.');
        setConnecting(false);
      };

      rtcRef.current = ws;
    } catch (err) {
      setError(`Voice setup failed: ${err}`);
      setConnecting(false);
    }
  }, [sessionId]);

  const handleRealtimeEvent = useCallback((data: { type: string; [key: string]: unknown }) => {
    switch (data.type) {
      case 'input_audio_buffer.speech_started':
        setOrbState('listening');
        break;

      case 'input_audio_buffer.speech_stopped':
        setOrbState('idle');
        break;

      case 'response.audio.delta':
        setOrbState('speaking');
        break;

      case 'response.audio.done':
        setOrbState('listening');
        break;

      case 'conversation.item.input_audio_transcription.completed': {
        const text = (data as { transcript?: string }).transcript || '';
        if (text) {
          setTranscript(prev => [...prev, { role: 'user', text }]);
          // Persist to backend
          forgeWs.send({
            action: 'transcript',
            session_id: sessionId,
            role: 'user',
            content: text,
          });
        }
        break;
      }

      case 'response.audio_transcript.done': {
        const text = (data as { transcript?: string }).transcript || '';
        if (text) {
          setTranscript(prev => [...prev, { role: 'assistant', text }]);
          forgeWs.send({
            action: 'transcript',
            session_id: sessionId,
            role: 'assistant',
            content: text,
          });
        }
        break;
      }

      case 'response.function_call_arguments.done': {
        // Tool call from GPT-4o - relay to backend
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
        setError(msg);
        break;
      }
    }
  }, [sessionId]);

  function disconnectRealtime() {
    if (rtcRef.current) {
      rtcRef.current.close();
      rtcRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
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
        <h3 className="text-lg font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
          Microphone access needed
        </h3>
        <p className="text-sm mb-4 max-w-sm" style={{ color: 'var(--color-text-muted)' }}>
          To use voice mode, allow microphone access in your browser settings, then try again.
        </p>
        <div className="flex gap-3">
          <button
            onClick={handleRetry}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white"
            style={{ backgroundColor: 'var(--color-primary)' }}
          >
            Try Again
          </button>
          <button
            onClick={onExit}
            className="px-4 py-2 rounded-lg text-sm font-medium border"
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
            <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Connecting voice...</span>
          </div>
        ) : (
          <VoiceOrb state={orbState} audioLevel={audioLevel} />
        )}
      </div>

      {/* Status text */}
      <div className="text-center mb-4" aria-live="polite">
        {error ? (
          <div>
            <p className="text-sm mb-2" style={{ color: 'var(--color-error)' }}>{error}</p>
            <button
              onClick={handleRetry}
              className="text-sm font-medium"
              style={{ color: 'var(--color-primary)' }}
            >
              Try again
            </button>
          </div>
        ) : (
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
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
            className={`mb-2 text-sm ${entry.role === 'user' ? 'text-right' : 'text-left'}`}
          >
            <span
              className={`inline-block px-3 py-2 rounded-2xl ${
                entry.role === 'user'
                  ? 'bg-[var(--color-user-bubble)]'
                  : ''
              }`}
              style={{ color: 'var(--color-text-primary)', maxWidth: '80%' }}
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
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm border transition-colors"
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
