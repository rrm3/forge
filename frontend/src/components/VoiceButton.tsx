/**
 * Voice input button with recording UI.
 *
 * States:
 * - idle: Gradient mic button (Voice Orb aesthetic) with pulse ring
 * - recording: Full-width timeline with cancel (X) and stop (Check) buttons
 * - processing: Timeline with spinner while transcribing
 *
 * Features:
 * - CapsLock keyboard shortcut (smart detection: toggle vs push-to-talk)
 * - Cursor-position transcript insertion
 * - prefers-reduced-motion support
 * - Inline error states (no modals)
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Mic, X, Check, Loader2 } from 'lucide-react';
import { useVoiceRecorder } from '../hooks/useVoiceRecorder';

interface VoiceButtonProps {
  onTranscribedText?: (text: string, cursorPosition?: number) => void;
  disabled?: boolean;
  onRecordingStateChange?: (isRecording: boolean) => void;
  textareaRef?: React.RefObject<HTMLTextAreaElement | null>;
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

interface TimelineSegment {
  timestamp: number;
  level: number;
}

function amplifyLevel(level: number, maxLevel: number): number {
  let amplified;
  if (maxLevel > 0.1) {
    amplified = level / maxLevel;
  } else {
    amplified = level * 5;
  }
  amplified = Math.pow(amplified, 0.7) * 1.3;
  return Math.min(1, amplified);
}

/**
 * Canvas-based waveform timeline. New bars appear at right edge, slide left.
 */
function Timeline({ segments, className }: { segments: TimelineSegment[]; className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewportWidth, setViewportWidth] = useState(0);
  const maxLevelRef = useRef(0);

  // Update max level with decay - use ref to avoid render loop
  if (segments.length === 0) {
    maxLevelRef.current = 0;
  } else {
    const latestLevel = segments[segments.length - 1].level;
    const decayedMax = maxLevelRef.current * 0.995;
    maxLevelRef.current = Math.max(latestLevel, decayedMax);
  }

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const updateWidth = () => setViewportWidth(container.clientWidth);
    updateWidth();
    const resizeObserver = new ResizeObserver(updateWidth);
    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || viewportWidth === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const canvasHeight = 40;
    const barWidth = 4;
    const maxBars = Math.floor(viewportWidth / barWidth);

    if (canvas.width !== viewportWidth || canvas.height !== canvasHeight) {
      canvas.width = viewportWidth;
      canvas.height = canvasHeight;
      canvas.style.width = `${viewportWidth}px`;
      canvas.style.height = `${canvasHeight}px`;
    }

    ctx.clearRect(0, 0, viewportWidth, canvasHeight);
    const centerY = canvasHeight / 2;
    const recentSegments = segments.slice(-maxBars);

    recentSegments.forEach((segment, index) => {
      const x = viewportWidth - (recentSegments.length - index) * barWidth;
      const level = segment.level;

      if (level < 0.02) {
        // Silence dot
        ctx.fillStyle = '#94A3B8';
        ctx.beginPath();
        ctx.arc(x + 1, centerY, 1.5, 0, Math.PI * 2);
        ctx.fill();
      } else {
        // Speech bar
        const amplified = amplifyLevel(level, maxLevelRef.current);
        const barHeight = Math.max(4, amplified * 32);
        ctx.fillStyle = '#159AC9';
        ctx.fillRect(x, centerY - barHeight / 2, 2, barHeight);
      }
    });
  }, [segments, viewportWidth]);

  return (
    <div
      ref={containerRef}
      className={`flex-1 min-w-0 overflow-hidden flex items-center ${className || ''}`}
      aria-hidden="true"
    >
      <canvas ref={canvasRef} className="w-full" style={{ height: '40px' }} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Gradient mic button styles (injected once)                         */
/* ------------------------------------------------------------------ */

const STYLE_ID = 'voice-button-styles';

function ensureStyles() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) return;

  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    @keyframes voice-gradient-rotate {
      from { --voice-angle: 0deg; }
      to   { --voice-angle: 360deg; }
    }

    @keyframes voice-pulse-ring {
      0%, 100% { transform: scale(1); opacity: 0.6; }
      50%      { transform: scale(1.18); opacity: 0; }
    }

    @keyframes voice-error-fade {
      0%   { opacity: 1; }
      75%  { opacity: 1; }
      100% { opacity: 0; }
    }

    @property --voice-angle {
      syntax: '<angle>';
      initial-value: 0deg;
      inherits: false;
    }

    .voice-mic-gradient {
      background: conic-gradient(
        from var(--voice-angle, 0deg),
        #22D3EE,
        #818CF8,
        #C084FC,
        #38BDF8,
        #22D3EE
      );
      animation: voice-gradient-rotate 4s linear infinite;
    }

    .voice-pulse-ring {
      animation: voice-pulse-ring 2s ease-in-out infinite;
    }

    .voice-error-fade {
      animation: voice-error-fade 4s ease-out forwards;
    }

    /* Focus ring */
    .voice-mic-btn:focus-visible {
      outline: 2px solid #159AC9;
      outline-offset: 2px;
    }

    /* Reduced motion: disable gradient rotation + pulse */
    @media (prefers-reduced-motion: reduce) {
      .voice-mic-gradient {
        animation: none;
        background: conic-gradient(
          from 0deg,
          #22D3EE,
          #818CF8,
          #C084FC,
          #38BDF8,
          #22D3EE
        );
      }
      .voice-pulse-ring {
        animation: none;
      }
    }

    /* Recording overlay transition */
    .voice-recording-overlay {
      transition: opacity 200ms ease-out, transform 200ms ease-out;
    }
  `;
  document.head.appendChild(style);
}

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */

const CAPSLOCK_HOLD_THRESHOLD = 500; // ms

/* ------------------------------------------------------------------ */
/* Component                                                          */
/* ------------------------------------------------------------------ */

const API_BASE = import.meta.env.VITE_API_URL || '';

export function VoiceButton({
  onTranscribedText,
  disabled = false,
  onRecordingStateChange,
  textareaRef,
}: VoiceButtonProps) {
  const {
    state,
    audioBlob,
    duration,
    audioLevel,
    error,
    startRecording,
    stopRecording,
    cancelRecording,
  } = useVoiceRecorder();
  const [isTranscribing, setIsTranscribing] = useState(false);
  const processedBlobRef = useRef<Blob | null>(null);
  const [timelineSegments, setTimelineSegments] = useState<TimelineSegment[]>([]);
  const [transcribeError, setTranscribeError] = useState<string | null>(null);
  const [micError, setMicError] = useState<string | null>(null);

  // CapsLock state tracking
  const capsDownTimeRef = useRef<number | null>(null);
  const isRecordingViaCapslockRef = useRef(false);

  // Inject global styles on mount
  useEffect(() => {
    ensureStyles();
  }, []);

  // Track audio levels for timeline
  useEffect(() => {
    if (state === 'recording') {
      setTimelineSegments((prev) => [...prev, { timestamp: duration, level: audioLevel }]);
    } else if (state === 'idle') {
      setTimelineSegments([]);
    }
  }, [state, duration, audioLevel]);

  // Notify parent of recording state
  useEffect(() => {
    const isRecording = state === 'recording' || state === 'processing' || isTranscribing;
    onRecordingStateChange?.(isRecording);
  }, [state, isTranscribing, onRecordingStateChange]);

  // Read cursor position from textarea at the moment recording stops
  const cursorPosRef = useRef<number | undefined>(undefined);

  const captureAndStop = useCallback(() => {
    // Capture cursor position before transcript arrives
    if (textareaRef?.current) {
      cursorPosRef.current = textareaRef.current.selectionStart ?? undefined;
    } else {
      cursorPosRef.current = undefined;
    }
    stopRecording();
  }, [stopRecording, textareaRef]);

  // Transcribe when recording stops
  useEffect(() => {
    if (audioBlob && !isTranscribing && audioBlob !== processedBlobRef.current) {
      processedBlobRef.current = audioBlob;
      setIsTranscribing(true);
      setTranscribeError(null);
      setMicError(null);

      const savedCursorPos = cursorPosRef.current;

      (async () => {
        try {
          const formData = new FormData();
          const ext = audioBlob.type.includes('mp4') ? 'mp4' : 'webm';
          formData.append('file', audioBlob, `recording.${ext}`);

          const token = localStorage.getItem('oidc_id_token');
          const response = await fetch(`${API_BASE}/api/transcribe`, {
            method: 'POST',
            headers: token ? { 'Authorization': `Bearer ${token}` } : {},
            body: formData,
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Transcription failed');
          }

          const data = await response.json();
          if (data.text && onTranscribedText) {
            onTranscribedText(data.text, savedCursorPos);
          }
        } catch (err) {
          console.error('Transcription error:', err);
          setTranscribeError(err instanceof Error ? err.message : 'Transcription failed');
        } finally {
          setIsTranscribing(false);
        }
      })();
    }
  }, [audioBlob, isTranscribing, onTranscribedText]);

  // Categorize errors from the hook into mic-specific errors
  useEffect(() => {
    if (!error) {
      setMicError(null);
      return;
    }
    if (error.includes('permission') || error.includes('Permission') || error.includes('denied')) {
      setMicError('permission');
    } else if (error.includes('No microphone') || error.includes('NotFound')) {
      setMicError('not-found');
    } else {
      setMicError('generic');
    }
  }, [error]);

  // Auto-fade transcription errors after 4s
  useEffect(() => {
    if (!transcribeError) return;
    const timer = setTimeout(() => setTranscribeError(null), 4000);
    return () => clearTimeout(timer);
  }, [transcribeError]);

  const isRecording = state === 'recording' || state === 'processing' || isTranscribing;

  // ---- CapsLock keyboard shortcut ----
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.code !== 'CapsLock') return;
      if (disabled) return;

      // Prevent default to avoid toggling CapsLock on the system
      e.preventDefault();

      // Already tracking a press, ignore repeat
      if (capsDownTimeRef.current !== null) return;

      capsDownTimeRef.current = Date.now();

      // If currently recording (toggle mode started it), a quick press will stop it
      // But we wait for keyup to decide
    }

    function handleKeyUp(e: KeyboardEvent) {
      if (e.code !== 'CapsLock') return;
      e.preventDefault();

      const downTime = capsDownTimeRef.current;
      capsDownTimeRef.current = null;

      if (downTime === null) return;

      const holdDuration = Date.now() - downTime;

      if (state === 'recording' || state === 'processing') {
        // We were recording, stop now (either toggle-off or push-to-talk release)
        captureAndStop();
        isRecordingViaCapslockRef.current = false;
      } else if (state === 'idle' && !isTranscribing) {
        if (holdDuration < CAPSLOCK_HOLD_THRESHOLD) {
          // Quick press: toggle on - will be toggled off on next press
          startRecording();
          isRecordingViaCapslockRef.current = true;
        }
        // For hold mode, we don't start here - we start on keydown timeout below
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('keyup', handleKeyUp);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('keyup', handleKeyUp);
    };
  }, [state, isTranscribing, disabled, startRecording, captureAndStop]);

  // Push-to-talk: if CapsLock is held past threshold, start recording
  useEffect(() => {
    if (disabled) return;
    if (state !== 'idle' || isTranscribing) return;

    const interval = setInterval(() => {
      const downTime = capsDownTimeRef.current;
      if (downTime === null) return;
      if (Date.now() - downTime >= CAPSLOCK_HOLD_THRESHOLD && !isRecordingViaCapslockRef.current) {
        isRecordingViaCapslockRef.current = true;
        startRecording();
      }
    }, 50);

    return () => clearInterval(interval);
  }, [state, isTranscribing, disabled, startRecording]);

  const tooltipText = 'Record voice message (CapsLock)';

  // ---- Render: Error display ----
  const renderError = () => {
    if (micError === 'permission') {
      return (
        <div
          className="text-xs mt-1"
          style={{ color: 'var(--color-error, #DC2626)' }}
          role="alert"
        >
          Microphone access needed. Enable in browser settings.{' '}
          <button
            onClick={() => {
              setMicError(null);
              startRecording();
            }}
            className="underline font-medium"
            style={{ color: 'var(--color-error, #DC2626)' }}
          >
            Try again
          </button>
        </div>
      );
    }
    if (micError === 'not-found') {
      return (
        <div
          className="text-xs mt-1"
          style={{ color: 'var(--color-error, #DC2626)' }}
          role="alert"
        >
          No microphone detected. You can type your response instead.
        </div>
      );
    }
    if (micError === 'generic' && error) {
      return (
        <div
          className="text-xs mt-1"
          style={{ color: 'var(--color-error, #DC2626)' }}
          role="alert"
        >
          {error}
        </div>
      );
    }
    if (transcribeError) {
      return (
        <div
          className="text-xs mt-1 voice-error-fade"
          style={{ color: 'var(--color-error, #DC2626)' }}
          role="alert"
        >
          {transcribeError}
        </div>
      );
    }
    return null;
  };

  // ---- Render: Idle state (simple icon button, matches acumentum) ----
  if (!isRecording) {
    return (
      <div className="inline-flex flex-col items-center">
        <button
          onClick={startRecording}
          disabled={disabled}
          className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors duration-150 hover:bg-[var(--color-surface-raised)]"
          style={{ color: 'var(--color-text-muted)' }}
          title={tooltipText}
          aria-label="Record voice message (CapsLock)"
        >
          <Mic className="w-5 h-5" strokeWidth={1.5} />
        </button>
        {renderError()}
      </div>
    );
  }

  // ---- Render: Recording state ----
  // The check button stays in the SAME position as the idle mic button.
  // Waveform + cancel expand to the left.
  if (state === 'recording') {
    return (
      <div className="voice-recording-overlay flex items-center gap-2 w-full">
        <button
          onClick={cancelRecording}
          className="voice-mic-btn flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center border transition-colors"
          style={{
            borderColor: 'var(--color-border)',
            color: 'var(--color-text-muted)',
          }}
          aria-label="Cancel recording"
        >
          <X className="w-3.5 h-3.5" strokeWidth={2} />
        </button>

        <Timeline segments={timelineSegments} />

        <span
          className="text-xs font-medium flex-shrink-0 tabular-nums"
          style={{
            color: 'var(--color-text-muted)',
            fontFamily: 'var(--font-mono, "Geist Mono", monospace)',
          }}
          aria-live="polite"
        >
          {formatDuration(duration)}
        </span>

        {/* Check button - same size and style as idle mic */}
        <button
          onClick={captureAndStop}
          className="voice-mic-btn flex-shrink-0 w-14 h-14 md:w-10 md:h-10 rounded-full flex items-center justify-center text-white transition-colors"
          style={{ backgroundColor: 'var(--color-primary)' }}
          aria-label="Stop recording"
          aria-pressed="true"
        >
          <Check className="w-5 h-5" strokeWidth={2} />
        </button>
      </div>
    );
  }

  // ---- Render: Processing / Transcribing ----
  // Spinner stays in the same position as mic/check button
  return (
    <div className="voice-recording-overlay flex items-center gap-2 w-full">
      <Timeline segments={timelineSegments} className="opacity-50" />
      <div
        className="flex-shrink-0 w-14 h-14 md:w-10 md:h-10 rounded-full flex items-center justify-center"
        style={{ backgroundColor: 'var(--color-primary-subtle, #E8F4F8)' }}
      >
        <Loader2
          className="w-5 h-5 animate-spin"
          style={{ color: 'var(--color-primary)' }}
        />
      </div>
    </div>
  );
}
