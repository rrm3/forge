/**
 * Voice Mode - uses @openai/agents RealtimeSession with WebRTC.
 *
 * The SDK handles all audio capture, playback, echo cancellation,
 * and VAD. We just configure the session and listen for events.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { MicOff, Square, Type, Pause, Play } from 'lucide-react';
import { RealtimeSession, RealtimeAgent, OpenAIRealtimeWebRTC, tool } from '@openai/agents/realtime';
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

export function VoiceMode({ sessionId, sessionType, onExit, transcript: externalTranscript, onTranscriptUpdate }: VoiceModeProps) {
  const [orbState, setOrbState] = useState<OrbState>('idle');
  const [audioLevel, setAudioLevel] = useState(0);
  const [transcript, setTranscript] = useState<{ role: string; text: string }[]>(externalTranscript || []);
  const [error, setError] = useState<string | null>(null);
  const [micDenied, setMicDenied] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [streamingText, setStreamingText] = useState('');
  const [paused, setPaused] = useState(false);

  const sessionRef = useRef<RealtimeSession | null>(null);
  const transportRef = useRef<OpenAIRealtimeWebRTC | null>(null);

  useEffect(() => { onTranscriptUpdate?.(transcript); }, [transcript, onTranscriptUpdate]);

  // Request ephemeral token and connect
  useEffect(() => {
    let cancelled = false;

    const unsubMessage = forgeWs.onMessage((msg: ServerMessage) => {
      if (cancelled) return;
      if (msg.type === 'voice_token' && 'session_id' in msg && msg.session_id === sessionId) {
        if (!sessionRef.current) {
          connectWithToken(msg.token);
        }
      }
      // Tool results from backend - relay to the session
      if (msg.type === 'tool_result' && 'session_id' in msg && msg.session_id === sessionId) {
        // The SDK handles tool results internally via its tool definitions
        // We relay via a different mechanism (see tool definitions below)
      }
    });

    forgeWs.requestVoiceSession(sessionId, sessionType);

    return () => {
      cancelled = true;
      unsubMessage();
      cleanup();
    };
  }, [sessionId, sessionType]);

  async function connectWithToken(token: string) {
    try {
      // Check mic access first
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(t => t.stop()); // Release immediately, SDK will request again
      } catch {
        setMicDenied(true);
        setConnecting(false);
        return;
      }

      // Create agent with tools that relay to our Forge backend
      const agent = new RealtimeAgent({
        name: 'forge',
        instructions: 'Follow the instructions from the session configuration.',
        tools: [
          tool({
            name: 'search',
            description: 'Search the knowledge base',
            parameters: { type: 'object' as const, properties: { query: { type: 'string' as const } }, required: ['query'] as const },
            execute: async (_ctx, args) => {
              return await relayToolToBackend('search', args as Record<string, unknown>);
            },
          }),
          tool({
            name: 'read_profile',
            description: 'Read the user profile',
            parameters: { type: 'object' as const, properties: {} },
            execute: async (_ctx, _args) => {
              return await relayToolToBackend('read_profile', {});
            },
          }),
          tool({
            name: 'update_profile',
            description: 'Update the user profile',
            parameters: { type: 'object' as const, properties: { fields: { type: 'object' as const } }, required: ['fields'] as const },
            execute: async (_ctx, args) => {
              return await relayToolToBackend('update_profile', args as Record<string, unknown>);
            },
          }),
          tool({
            name: 'save_journal',
            description: 'Save a journal entry',
            parameters: { type: 'object' as const, properties: { content: { type: 'string' as const } }, required: ['content'] as const },
            execute: async (_ctx, args) => {
              return await relayToolToBackend('save_journal', args as Record<string, unknown>);
            },
          }),
        ],
      });

      // WebRTC transport with correct endpoint for ephemeral tokens
      // Ephemeral tokens use /v1/realtime?model=... not /v1/realtime/calls
      const transport = new OpenAIRealtimeWebRTC({
        baseUrl: 'https://api.openai.com/v1/realtime',
      });
      transportRef.current = transport;

      // Create session - agent is first arg, options second
      const session = new RealtimeSession(agent, {
        transport,
        model: 'gpt-4o-realtime-preview-2024-12-17',
      });
      sessionRef.current = session;

      // Event listeners
      session.on('agent_start', () => {
        setOrbState('speaking');
      });

      session.on('agent_end', () => {
        setOrbState('listening');
      });

      session.on('audio_start', () => {
        setOrbState('speaking');
      });

      session.on('audio_stopped', () => {
        setOrbState('listening');
      });

      session.on('audio_interrupted', () => {
        setOrbState('listening');
      });

      session.on('agent_tool_start', () => {
        setOrbState('tool_call');
      });

      session.on('agent_tool_end', () => {
        setOrbState('idle');
      });

      session.on('history_updated', (history) => {
        // Convert history to our transcript format
        const entries: { role: string; text: string }[] = [];
        for (const item of history) {
          if (item.type === 'message') {
            const role = item.role === 'user' ? 'user' : 'assistant';
            const text = item.content?.map((c: { text?: string; transcript?: string }) => c.text || c.transcript || '').join('') || '';
            if (text.trim()) {
              entries.push({ role, text: text.trim() });
            }
          }
        }
        setTranscript(entries);
        setStreamingText('');
      });

      session.on('transport_event', (event) => {
        if (event.type === 'transcript_delta') {
          setStreamingText(prev => prev + ((event as { delta?: string }).delta || ''));
        }
      });

      session.on('error', (err) => {
        const msg = err?.error ? String(err.error) : 'Voice error';
        console.error('RealtimeSession error:', msg);
        if (!msg.includes('active response')) {
          setError(msg);
        }
      });

      // Connect with the ephemeral token
      await session.connect({ apiKey: token });
      setConnecting(false);
      setOrbState('listening');

      // Trigger initial greeting
      transport.sendEvent({ type: 'response.create' });

    } catch (err) {
      console.error('Voice connection failed:', err);
      setError(`Connection failed: ${err}`);
      setConnecting(false);
    }
  }

  // Relay tool calls to our backend via the Forge WebSocket
  function relayToolToBackend(toolName: string, args: Record<string, unknown>): Promise<string> {
    return new Promise((resolve) => {
      const callId = `voice_${Date.now()}`;

      const unsub = forgeWs.onMessage((msg: ServerMessage) => {
        if (msg.type === 'tool_result' && 'tool_call_id' in msg && (msg as { tool_call_id: string }).tool_call_id === callId) {
          unsub();
          resolve((msg as { result: string }).result || 'Done');
        }
      });

      forgeWs.send({
        action: 'tool_call',
        session_id: sessionId,
        tool: toolName,
        tool_call_id: callId,
        args,
      });

      // Timeout after 15s
      setTimeout(() => { unsub(); resolve('Tool call timed out'); }, 15000);
    });
  }

  function togglePause() {
    const transport = transportRef.current;
    if (transport) {
      const newPaused = !paused;
      transport.mute(newPaused);
      setPaused(newPaused);
    }
  }

  function cleanup() {
    if (sessionRef.current) {
      try { sessionRef.current.close(); } catch {}
      sessionRef.current = null;
    }
    if (transportRef.current) {
      try { transportRef.current.close(); } catch {}
      transportRef.current = null;
    }
  }

  // Persist transcript to backend when it changes
  useEffect(() => {
    if (transcript.length > 0) {
      const last = transcript[transcript.length - 1];
      forgeWs.send({
        action: 'transcript',
        session_id: sessionId,
        role: last.role,
        content: last.text,
      });
    }
  }, [transcript.length, sessionId]);

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

      <div className="text-center mb-4" aria-live="polite">
        {error ? (
          <div>
            <p className="text-sm font-medium mb-2" style={{ color: 'var(--color-error)' }}>{error}</p>
            <button onClick={() => { setError(null); setConnecting(true); cleanup(); forgeWs.requestVoiceSession(sessionId, sessionType); }}
              className="text-sm font-semibold" style={{ color: 'var(--color-primary)' }}>Try again</button>
          </div>
        ) : (
          <p className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
            {paused ? 'Paused' :
             orbState === 'listening' ? 'Listening...' :
             orbState === 'speaking' ? 'AI is speaking...' :
             orbState === 'tool_call' ? 'Looking something up...' :
             orbState === 'reconnecting' ? 'Reconnecting...' : 'Ready'}
          </p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto w-full max-w-2xl px-4">
        {transcript.map((entry, i) => (
          <div key={i} className={`mb-3 ${entry.role === 'user' ? 'text-right' : 'text-left'}`}>
            <span className={`inline-block px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${entry.role === 'user' ? 'bg-[var(--color-user-bubble)]' : ''}`}
              style={{ color: 'var(--color-text-primary)', maxWidth: '80%', display: 'inline-block' }}>
              {entry.text}
            </span>
          </div>
        ))}
        {streamingText && (
          <div className="mb-3 text-left">
            <span className="inline-block px-4 py-2.5 rounded-2xl text-sm leading-relaxed"
              style={{ color: 'var(--color-text-primary)', maxWidth: '80%', display: 'inline-block' }}>
              {streamingText}
            </span>
          </div>
        )}
      </div>

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
          title={paused ? 'Resume' : 'Pause'}>
          {paused ? <Play className="w-5 h-5" strokeWidth={1.5} /> : <Pause className="w-5 h-5" strokeWidth={1.5} />}
        </button>
        <button onClick={() => { cleanup(); onExit(); }}
          className="flex items-center justify-center w-12 h-12 rounded-full text-white"
          style={{ backgroundColor: 'var(--color-error)' }}
          aria-label="Stop">
          <Square className="w-5 h-5" fill="currentColor" strokeWidth={0} />
        </button>
      </div>
    </div>
  );
}
