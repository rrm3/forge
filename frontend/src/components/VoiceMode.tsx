/**
 * Voice Mode - OpenAI Realtime API via WebRTC.
 *
 * Based on the openai-realtime-console reference implementation:
 * - WebRTC PeerConnection for audio (native echo cancellation)
 * - Data channel for events (transcripts, tool calls)
 * - Ephemeral token from server-side session creation
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

const REALTIME_MODEL = 'gpt-4o-realtime-preview-2024-12-17';

export function VoiceMode({ sessionId, sessionType, onExit, transcript: externalTranscript, onTranscriptUpdate }: VoiceModeProps) {
  const [orbState, setOrbState] = useState<OrbState>('idle');
  const [audioLevel, setAudioLevel] = useState(0);
  const [transcript, setTranscript] = useState<{ role: string; text: string }[]>(externalTranscript || []);
  const [error, setError] = useState<string | null>(null);
  const [micDenied, setMicDenied] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [streamingText, setStreamingText] = useState('');
  const [paused, setPaused] = useState(false);
  const [micGated, setMicGated] = useState(false);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dcRef = useRef<RTCDataChannel | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);

  useEffect(() => { onTranscriptUpdate?.(transcript); }, [transcript, onTranscriptUpdate]);

  // Request ephemeral token and connect
  useEffect(() => {
    let cancelled = false;

    const unsubMessage = forgeWs.onMessage((msg: ServerMessage) => {
      if (cancelled) return;
      if (msg.type === 'voice_token' && 'session_id' in msg && msg.session_id === sessionId) {
        if (!pcRef.current) {
          const m = msg as { token: string; instructions?: string; tools?: unknown[] };
          connectWebRTC(m.token, m.instructions || '', m.tools || []);
        }
      }
      // Tool results are handled by executeToolViaBackend's own message listener
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

  // ---- WebRTC connection (from openai-realtime-console reference) ----

  async function connectWebRTC(token: string, instructions: string, tools: unknown[]) {
    try {
      // 1. Get microphone
      let localStream: MediaStream;
      try {
        localStream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
      } catch {
        setMicDenied(true);
        setConnecting(false);
        return;
      }
      localStreamRef.current = localStream;

      // Set up analyser for orb visualization
      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(localStream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      // 2. Create PeerConnection
      const pc = new RTCPeerConnection();
      pcRef.current = pc;

      pc.addEventListener('connectionstatechange', () => {
        if (pc.connectionState === 'connected') {
          setConnecting(false);
          setOrbState('listening');
        }
        if (pc.connectionState === 'failed' || pc.connectionState === 'closed') {
          setOrbState('reconnecting');
        }
      });

      // 3. Play remote audio (AI's voice) via an <audio> element
      pc.addEventListener('track', (event) => {
        const [remoteStream] = event.streams;
        if (!remoteAudioRef.current || !remoteStream) return;
        remoteAudioRef.current.srcObject = remoteStream;
        remoteAudioRef.current.play().catch(() => {});
      });

      // 4. Add local mic tracks
      for (const track of localStream.getAudioTracks()) {
        pc.addTrack(track, localStream);
      }

      // 5. Create data channel for events
      const dc = pc.createDataChannel('oai-events');
      dcRef.current = dc;

      dc.addEventListener('open', () => {
        // Configure the session with instructions, tools, and VAD settings
        // (GA endpoint creates bare tokens - config is sent via data channel)
        dc.send(JSON.stringify({
          type: 'session.update',
          session: {
            type: 'realtime',
            instructions: instructions || undefined,
            tools: tools.length > 0 ? tools : undefined,
            audio: {
              input: {
                transcription: { model: 'whisper-1' },
                noise_reduction: { type: 'far_field' },
                turn_detection: {
                  type: 'server_vad',
                  threshold: 0.7,
                  silence_duration_ms: 1000,
                  prefix_padding_ms: 400,
                  create_response: true,
                  interrupt_response: true,
                },
              },
            },
          },
        }));

        // Trigger initial greeting
        dc.send(JSON.stringify({ type: 'response.create' }));
      });

      dc.addEventListener('message', (messageEvent) => {
        try {
          const event = JSON.parse(messageEvent.data);
          handleServerEvent(event);
        } catch {}
      });

      // 6. SDP offer/answer exchange
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await waitForIceGathering(pc);

      const url = new URL('https://api.openai.com/v1/realtime/calls');
      url.searchParams.set('model', REALTIME_MODEL);

      const sdpResponse = await fetch(url.toString(), {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/sdp',
        },
        body: pc.localDescription?.sdp,
      });

      if (!sdpResponse.ok) {
        const errText = await sdpResponse.text();
        throw new Error(`SDP exchange failed: ${sdpResponse.status} ${errText}`);
      }

      const answerSdp = await sdpResponse.text();
      await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });

    } catch (err) {
      console.error('Voice connection failed:', err);
      setError(err instanceof Error ? err.message : String(err));
      setConnecting(false);
    }
  }

  function waitForIceGathering(pc: RTCPeerConnection): Promise<void> {
    return new Promise((resolve) => {
      if (pc.iceGatheringState === 'complete') {
        resolve();
        return;
      }
      const check = () => {
        if (pc.iceGatheringState === 'complete') {
          pc.removeEventListener('icegatheringstatechange', check);
          resolve();
        }
      };
      pc.addEventListener('icegatheringstatechange', check);
      // Fallback timeout
      setTimeout(resolve, 3000);
    });
  }

  // ---- Handle server events from data channel ----

  function handleServerEvent(event: { type: string; [key: string]: unknown }) {
    switch (event.type) {
      case 'input_audio_buffer.speech_started':
        setOrbState('listening');
        break;

      case 'input_audio_buffer.speech_stopped':
        setOrbState('idle');
        break;

      case 'response.audio.delta':
        setOrbState('speaking');
        // Mute mic while AI speaks to prevent echo pickup
        setMicGated(true);
        localStreamRef.current?.getAudioTracks().forEach(t => { t.enabled = false; });
        break;

      case 'response.audio.done':
        // Re-enable mic after AI finishes speaking (short delay for tail audio)
        setTimeout(() => {
          if (!pausedRef.current) {
            setMicGated(false);
            localStreamRef.current?.getAudioTracks().forEach(t => { t.enabled = true; });
          }
          setOrbState('listening');
        }, 300);
        break;

      case 'response.output_audio_transcript.delta':
        setStreamingText(prev => prev + (String(event.delta ?? '')));
        break;

      case 'response.output_audio_transcript.done':
        setStreamingText('');
        {
          const text = String(event.transcript ?? '').trim();
          if (text) {
            setTranscript(prev => [...prev, { role: 'assistant', text }]);
            forgeWs.send({ action: 'transcript', session_id: sessionId, role: 'assistant', content: text });
          }
        }
        break;

      case 'conversation.item.input_audio_transcription.completed':
        {
          const text = String(event.transcript ?? '').trim();
          if (text) {
            setTranscript(prev => {
              if (prev.length > 0 && prev[prev.length - 1].role === 'user') {
                return [...prev.slice(0, -1), { role: 'user', text }];
              }
              return [...prev, { role: 'user', text }];
            });
            forgeWs.send({ action: 'transcript', session_id: sessionId, role: 'user', content: text });
          }
        }
        break;

      case 'response.function_call_arguments.done':
        setOrbState('tool_call');
        {
          const callId = String(event.call_id ?? '');
          const name = String(event.name ?? '');
          const args = String(event.arguments ?? '{}');
          console.log(`Tool call: ${name} (${callId})`);
          // Execute tool via backend relay
          executeToolViaBackend(callId, name, args);
        }
        break;

      case 'error':
        {
          const msg = (event.error as { message?: string })?.message || JSON.stringify(event.error);
          console.error('Realtime error:', msg);
          if (!msg.includes('active response')) {
            setError(msg);
          }
        }
        break;
    }
  }

  // ---- Send events via data channel ----

  function sendEvent(event: Record<string, unknown>) {
    if (dcRef.current?.readyState === 'open') {
      dcRef.current.send(JSON.stringify(event));
    }
  }

  function sendToolResult(callId: string, result: string) {
    console.log(`Sending tool result for ${callId}: ${result.substring(0, 100)}...`);
    sendEvent({
      type: 'conversation.item.create',
      item: { type: 'function_call_output', call_id: callId, output: result },
    });
    sendEvent({ type: 'response.create' });
  }

  function executeToolViaBackend(callId: string, name: string, argsStr: string) {
    const localCallId = `voice_${Date.now()}`;

    const unsub = forgeWs.onMessage((msg: ServerMessage) => {
      if (msg.type === 'tool_result' && 'tool_call_id' in msg &&
          (msg as { tool_call_id: string }).tool_call_id === localCallId) {
        unsub();
        const result = (msg as { result: string }).result || 'Done';
        sendToolResult(callId, result);
      }
    });

    forgeWs.send({
      action: 'tool_call',
      session_id: sessionId,
      tool: name,
      tool_call_id: localCallId,
      args: JSON.parse(argsStr),
    });

    // Timeout - send empty result rather than hanging
    setTimeout(() => {
      unsub();
      sendToolResult(callId, 'Tool call timed out');
    }, 15000);
  }

  function togglePause() {
    const stream = localStreamRef.current;
    if (stream) {
      const newPaused = !paused;
      stream.getAudioTracks().forEach(t => { t.enabled = !newPaused; });
      setPaused(newPaused);
      if (!newPaused) setMicGated(false);
    }
  }

  function interrupt() {
    // Unmute mic and cancel AI's current response
    setMicGated(false);
    localStreamRef.current?.getAudioTracks().forEach(t => { t.enabled = true; });
    sendEvent({ type: 'response.cancel' });
    setOrbState('listening');
  }

  function cleanup() {
    if (dcRef.current) { try { dcRef.current.close(); } catch {} dcRef.current = null; }
    if (pcRef.current) { pcRef.current.close(); pcRef.current = null; }
    if (localStreamRef.current) { localStreamRef.current.getTracks().forEach(t => t.stop()); localStreamRef.current = null; }
    analyserRef.current = null;
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
      {/* Hidden audio element for AI voice playback */}
      <audio ref={remoteAudioRef} autoPlay style={{ display: 'none' }} />

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
          <>
            <p className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
              {paused ? 'Paused' :
               orbState === 'listening' ? 'Listening...' :
               orbState === 'speaking' ? 'AI is speaking... tap to interrupt' :
               orbState === 'tool_call' ? 'Looking something up...' :
               orbState === 'reconnecting' ? 'Reconnecting...' : 'Ready'}
            </p>
            {orbState === 'speaking' && !paused && (
              <button onClick={interrupt}
                className="mt-2 text-xs font-semibold px-3 py-1 rounded-full border"
                style={{ borderColor: 'var(--color-primary)', color: 'var(--color-primary)' }}>
                Interrupt
              </button>
            )}
          </>
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
