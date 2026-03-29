/**
 * IntakeView - Full-screen focused layout for first-run intake.
 *
 * Shows onboarding cards first, then transitions to chat with mic option.
 * No sidebar, no action buttons. TopBar persists across both states.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Square, Send, X, ArrowRight, Lightbulb, Compass, Star, Sunrise, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSession } from '../state/SessionContext';
import { MessageBubble, streamingMarkdownComponents } from './MessageBubble';
import { VoiceButton } from './VoiceButton';
import { OnboardingCards } from './OnboardingCards';
import { TopBar } from './TopBar';
import { IntakeDebugPanel } from './IntakeDebugPanel';
import { useAdminStore } from '../state/adminStore';
import { reevaluateIntake, skipIntake } from '../api/client';
import { getProgramWeek } from '../program';

interface IntakeViewProps {
  onComplete?: () => void;
  profile?: import('../api/types').UserProfile | null;
}

export function IntakeView({ onComplete, profile }: IntakeViewProps) {
  const navigate = useNavigate();
  const adminMode = useAdminStore((s) => s.adminMode);
  const { state, sendChatMessage, startTypedSession, cancelStreaming, deselectSession, selectSession } = useSession();
  const { messages = [], isStreaming, streamingText, activeSessionId, intakeComplete } = state;

  const [inputValue, setInputValue] = useState('');
  const [isVoiceRecording, setIsVoiceRecording] = useState(false);
  // Show onboarding cards only for Week 1 first-time users.
  // Week 2+ users skip cards entirely (they already know the app).
  // An intake session with message_count > 0 means the user is past the cards.
  const sessionsLoaded = state.sessionsLoaded;
  const currentWeek = getProgramWeek();
  const isReturningUser = currentWeek > 1;
  const intakeSessionHasMessages = state.sessions.some(
    (s) => s.type === 'intake' && (s.message_count ?? 0) > 0
  );
  const [cardsDismissed, setCardsDismissed] = useState(false);

  // Freeze the "has messages" check at the moment sessions first load.
  // Without this, the background preload (started on Card 1 for performance)
  // causes intakeSessionHasMessages to flip true mid-card-sequence, which
  // dismisses the cards before the user clicks "Let's go".
  const initialIntakeHasMessages = useRef<boolean | null>(null);
  if (sessionsLoaded && initialIntakeHasMessages.current === null) {
    initialIntakeHasMessages.current = intakeSessionHasMessages;
  }

  // Skip onboarding cards for Week 2+ or returning users with existing messages
  const showCards = !isReturningUser && !cardsDismissed && !(initialIntakeHasMessages.current ?? false);
  const [showCapsHint, setShowCapsHint] = useState(false);
  const capsHintDismissed = useRef(false);
  const inputValueRef = useRef(inputValue);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const intakeStarted = useRef(false);

  const sendCountRef = useRef(0);
  const reevaluateAttempted = useRef(false);
  const [skipping, setSkipping] = useState(false);
  const [showSkipModal, setShowSkipModal] = useState(false);

  const showSkipOption = !intakeComplete && !showCards;

  // Re-evaluate objectives on page reload for returning users with existing transcripts.
  // This lets the updated evaluation logic retroactively detect completed objectives.
  useEffect(() => {
    if (reevaluateAttempted.current || !sessionsLoaded) return;
    const intake = state.sessions.find((s) => s.type === 'intake');
    if (!intake || (intake.message_count ?? 0) < 5) return;
    reevaluateAttempted.current = true;
    reevaluateIntake().catch(() => {});
  }, [sessionsLoaded, state.sessions]);

  async function handleSkip() {
    setSkipping(true);
    try {
      await skipIntake();
      deselectSession();
      window.location.href = '/';
    } catch {
      setSkipping(false);
    }
  }

  // Pre-load: start the intake session on Card 1 so AI greeting is ready by "Let's go"
  function handleCardChange(cardIndex: number) {
    if (cardIndex >= 0 && !intakeStarted.current) {
      intakeStarted.current = true;
      startTypedSession('intake');
    }
  }

  function handleCardsComplete() {
    setCardsDismissed(true);
  }

  // If cards are skipped (returning user with existing intake that has messages),
  // select the existing session to resume the conversation.
  useEffect(() => {
    if (!showCards && !intakeStarted.current) {
      intakeStarted.current = true;
      if (intakeSessionHasMessages) {
        const existing = state.sessions.find((s) => s.type === 'intake');
        if (existing) {
          selectSession(existing.session_id);
        }
      } else {
        // No messages yet - cards will show, session pre-loads on card 1
      }
    }
  }, [showCards, intakeSessionHasMessages, state.sessions, selectSession]);

  function handleInputChange(v: string) {
    inputValueRef.current = v;
    setInputValue(v);
  }

  function handleTranscribedText(text: string, cursorPosition?: number) {
    const textarea = textareaRef.current;
    if (textarea && cursorPosition !== undefined) {
      const before = inputValue.substring(0, cursorPosition);
      const after = inputValue.substring(cursorPosition);
      const padBefore = before.length > 0 && !/\s$/.test(before) ? ' ' : '';
      const padAfter = after.length > 0 && !/^\s/.test(after) ? ' ' : '';
      const inserted = padBefore + text + padAfter;
      handleInputChange(before + inserted + after);
      requestAnimationFrame(() => {
        textarea.selectionStart = textarea.selectionEnd = cursorPosition + inserted.length;
        textarea.focus();
      });
    } else {
      handleInputChange(inputValue ? inputValue + ' ' + text : text);
      textareaRef.current?.focus();
    }
  }

  useEffect(() => {
    if (isVoiceRecording) return; // Don't resize while recording
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 184)}px`;
  }, [inputValue]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, streamingText, intakeComplete]);

  useEffect(() => {
    textareaRef.current?.focus();
  }, [activeSessionId]);

  // Show CapsLock hint after first AI message appears
  useEffect(() => {
    if (messages.length > 0 && !capsHintDismissed.current && !showCards) {
      setShowCapsHint(true);
    }
  }, [messages.length, showCards]);

  // Auto-dismiss CapsLock hint after 15 seconds
  useEffect(() => {
    if (!showCapsHint) return;
    const timer = setTimeout(() => {
      setShowCapsHint(false);
      capsHintDismissed.current = true;
    }, 15000);
    return () => clearTimeout(timer);
  }, [showCapsHint]);

  // Hide CapsLock hint when recording starts
  useEffect(() => {
    if (isVoiceRecording && showCapsHint) {
      setShowCapsHint(false);
      capsHintDismissed.current = true;
    }
  }, [isVoiceRecording, showCapsHint]);

  function dismissCapsHint() {
    setShowCapsHint(false);
    capsHintDismissed.current = true;
  }

  function handleContinue() {
    deselectSession();
    onComplete?.();
    navigate('/');
  }

  const handleSend = useCallback(() => {
    const text = inputValueRef.current.trim();
    if (!text || isStreaming) return;
    handleInputChange('');
    sendCountRef.current += 1;
    sendChatMessage(text);
  }, [isStreaming, sendChatMessage]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim() && !isStreaming) handleSend();
    }
  }

  const hasInput = inputValue.trim().length > 0;
  const showVoiceHint = sendCountRef.current < 3;
  const hintText = isVoiceRecording
    ? 'Recording... tap check to stop'
    : showVoiceHint
      ? 'Tap mic or press CapsLock to respond'
      : 'Enter to send, Shift+Enter for new line';

  // Wait for sessions to load before deciding what to show
  if (!sessionsLoaded) {
    return (
      <div className="h-screen flex flex-col" style={{ backgroundColor: 'var(--color-surface)' }}>
        <TopBar profile={profile} />
      </div>
    );
  }

  return (
    <div
      className="h-screen flex flex-col"
      style={{ backgroundColor: 'var(--color-surface)' }}
    >
      <TopBar profile={profile} />
      <IntakeDebugPanel />

      {showCards ? (
        <OnboardingCards onComplete={handleCardsComplete} onCardChange={handleCardChange} />
      ) : (
        <div className="flex-1 flex flex-col relative min-h-0">
          {/* Subtle gradient wash at top */}
          <div
            className="pointer-events-none absolute top-0 left-0 right-0 h-32 z-10"
            style={{
              background: 'linear-gradient(to bottom, rgba(34,211,238,0.03), rgba(129,140,248,0.02), transparent)',
            }}
          />

          {/* Skip button - escape valve */}
          {showSkipOption && (
            <div className="absolute top-3 right-4 z-20">
              <button
                onClick={() => setShowSkipModal(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                style={{
                  color: 'var(--color-text-secondary)',
                  backgroundColor: 'var(--color-surface-white)',
                  border: '1px solid var(--color-border)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-surface-hover, #F1F5F9)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-surface-white)';
                }}
              >
                Skip
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          )}

          {/* Skip confirmation modal */}
          {showSkipModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.4)' }} onClick={() => setShowSkipModal(false)}>
              <div
                onClick={(e) => e.stopPropagation()}
                className="rounded-xl border p-6 mx-4 max-w-lg w-full shadow-lg"
                style={{ backgroundColor: 'var(--color-surface-white)', borderColor: 'var(--color-border)' }}
              >
                <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                  Skip getting started?
                </h3>
                <p className="text-sm mb-3" style={{ color: 'var(--color-text-secondary)' }}>
                  This conversation helps us understand your role and goals so we can make better suggestions throughout the program. The more you share, the more relevant your experience will be.
                </p>
                <p className="text-sm mb-5" style={{ color: 'var(--color-text-secondary)' }}>
                  If you'd like to come back to this later, you can resume anytime by clicking <strong>Day 1 Getting Started</strong> in the sidebar.
                </p>
                <div className="flex gap-3 justify-end">
                  <button
                    onClick={() => setShowSkipModal(false)}
                    className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                    style={{ color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => { setShowSkipModal(false); handleSkip(); }}
                    disabled={skipping}
                    className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors"
                    style={{ backgroundColor: 'var(--color-primary)' }}
                  >
                    {skipping ? 'Skipping...' : 'Skip'}
                  </button>
                </div>
                <p className="text-xs mt-4 text-center" style={{ color: 'var(--color-text-placeholder)' }}>
                  Having a technical issue? <a href="mailto:aituesdayscompanion@digital-science.com" style={{ textDecoration: 'underline' }}>Email us</a> or post in <a href="https://digital-science.slack.com/archives/C0AH3SAFR50" target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'underline' }}><strong>#ai-tuesdays</strong></a> on Slack
                </p>
              </div>
            </div>
          )}

          {/* Scrollable messages area */}
          <div className="flex-1 overflow-y-auto min-h-0">
            <div className="max-w-2xl mx-auto px-4 py-4 space-y-1 min-h-full flex flex-col justify-end">
              {messages.filter((msg) => adminMode || (msg.role !== 'tool_call' && msg.role !== 'tool_result')).map((msg, i) => (
                <MessageBubble key={i} message={msg} />
              ))}

              {isStreaming && streamingText && (
                <div className="flex justify-start py-1">
                  <div className="max-w-[95%] md:max-w-[85%] prose prose-sm max-w-none px-4 py-3 rounded-2xl" style={{ color: 'var(--color-text-primary)', backgroundColor: 'var(--color-surface-white, #FFFFFF)', border: '1px solid var(--color-border, #E2E8F0)' }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={streamingMarkdownComponents}>
                      {streamingText}
                    </ReactMarkdown>
                  </div>
                </div>
              )}

              {isStreaming && (
                <div className="flex justify-start py-1">
                  <div className="px-1 py-1">
                    <div className="flex gap-1.5 items-center" role="status" aria-label="AI is thinking">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: 'var(--color-text-placeholder)', animation: 'bounce 1.4s ease-in-out infinite' }} />
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: 'var(--color-text-placeholder)', animation: 'bounce 1.4s ease-in-out 0.2s infinite' }} />
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: 'var(--color-text-placeholder)', animation: 'bounce 1.4s ease-in-out 0.4s infinite' }} />
                    </div>
                  </div>
                </div>
              )}

              {/* Completion card - week-aware */}
              {intakeComplete && !isStreaming && (
                <CompletionCard week={currentWeek} onContinue={handleContinue} />
              )}

              <div ref={bottomRef} />
            </div>
          </div>

          {/* Input area - hidden after completion, pinned to bottom */}
          {!intakeComplete && <div className="shrink-0 max-w-2xl mx-auto w-full px-4 pb-4">
            {/* CapsLock floating hint */}
            {showCapsHint && (
              <div className="flex justify-center mb-2">
                <div
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full"
                  style={{ backgroundColor: '#E8F4F8' }}
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
                    <rect x="1" y="1" width="14" height="14" rx="3" stroke="#159AC9" strokeWidth="1.2" opacity="0.7" />
                    <path d="M8 4L5 7.5H7V9.5H9V7.5H11L8 4Z" fill="#159AC9" opacity="0.7" />
                    <rect x="6" y="10.5" width="4" height="1.5" rx="0.5" fill="#159AC9" opacity="0.7" />
                  </svg>
                  <span style={{ color: '#159AC9', fontSize: 12, fontWeight: 500 }}>
                    Press CapsLock to speak your reply
                  </span>
                  <button
                    onClick={dismissCapsHint}
                    className="flex items-center justify-center"
                    style={{ color: '#94A3B8', cursor: 'pointer' }}
                    aria-label="Dismiss hint"
                  >
                    <X size={12} />
                  </button>
                </div>
              </div>
            )}

            <div
              className="relative rounded-xl border transition-all duration-200"
              style={{
                backgroundColor: 'var(--color-surface-white)',
                borderColor: 'var(--color-border)',
              }}
            >
              <div className="p-2 cursor-text" onClick={(e) => {
                if ((e.target as HTMLElement).tagName !== 'TEXTAREA') {
                  textareaRef.current?.focus();
                }
              }}>
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={inputValue}
                  onChange={(e) => handleInputChange(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type or tap mic to respond..."
                  className="w-full resize-none bg-transparent outline-none border-none text-base md:text-sm leading-6 p-1 pb-8 pr-24 overflow-y-auto"
                  style={{
                    color: 'var(--color-text-primary)',
                    minHeight: '40px',
                    maxHeight: '184px',
                    caretColor: 'var(--color-text-primary)',
                    opacity: isVoiceRecording ? 0 : 1,
                    pointerEvents: isVoiceRecording ? 'none' : undefined,
                  }}
                  aria-label="Intake response"
                />

                {/* Bottom buttons: voice (full-width when recording) + send/stop */}
                <div className={`absolute bottom-0 right-0 left-0 flex items-center pb-2 px-3 ${isVoiceRecording ? '' : 'justify-end'}`}>
                  <div className={`flex items-center ${isVoiceRecording ? 'w-full' : 'gap-1.5'}`}>
                    <VoiceButton
                      onTranscribedText={handleTranscribedText}
                      onRecordingStateChange={setIsVoiceRecording}
                      textareaRef={textareaRef}
                    />
                    {!isVoiceRecording && (
                      isStreaming ? (
                        <button
                          onClick={cancelStreaming}
                          className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors duration-150"
                          style={{ backgroundColor: 'var(--color-text-primary)', color: '#FFFFFF' }}
                          title="Stop"
                          aria-label="Stop generating"
                        >
                          <Square className="w-4 h-4" fill="currentColor" strokeWidth={0} />
                        </button>
                      ) : (
                        <button
                          onClick={handleSend}
                          disabled={!hasInput}
                          className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors duration-150"
                          style={{
                            backgroundColor: hasInput ? 'var(--color-text-primary)' : 'transparent',
                            color: hasInput ? '#FFFFFF' : 'var(--color-text-placeholder)',
                            cursor: hasInput ? 'pointer' : 'default',
                          }}
                          title="Send (Enter)"
                          aria-label="Send message"
                        >
                          <Send className="w-4 h-4" strokeWidth={1.5} />
                        </button>
                      )
                    )}
                  </div>
                </div>
              </div>
            </div>
            <p className="text-xs text-center mt-1.5" style={{ color: 'var(--color-text-placeholder)' }}>
              {hintText}
            </p>
          </div>}
        </div>
      )}
    </div>
  );
}


/* Week-aware completion card */

interface CompletionCardProps {
  week: number;
  onContinue: () => void;
}

// Weekly feature nudges - each week highlights a different app feature
const WEEKLY_NUDGES: Record<number, { Icon: typeof Lightbulb; text: string }> = {
  2: { Icon: Sparkles, text: 'Did you know you can share tips and tricks with your colleagues? When you discover something useful, tap "Share a tip" to help others learn from your experience.' },
  3: { Icon: Compass, text: 'Have a problem you keep running into? Try "I\'m stuck" to brainstorm AI solutions with your companion.' },
  4: { Icon: Sunrise, text: 'End your AI Tuesday with a quick wrap-up to reflect on what you learned and plan your next steps.' },
  5: { Icon: Star, text: 'Ready to go deeper? Use "Brainstorm" to explore a bigger AI opportunity for your team.' },
};

function CompletionCard({ week, onContinue }: CompletionCardProps) {
  if (week <= 1) {
    // Week 1: original full resource list
    return (
      <div
        className="my-4 mx-auto w-full rounded-xl border p-6"
        style={{
          backgroundColor: 'var(--color-surface-white)',
          borderColor: 'var(--color-border)',
        }}
      >
        <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
          You're all set!
        </h3>

        <p className="text-sm mb-4" style={{ color: 'var(--color-text-secondary)' }}>
          Here are some of the resources available in this app:
        </p>

        <div className="space-y-2 mb-4">
          {[
            { Icon: Lightbulb, text: 'Share a tip or trick with your colleagues' },
            { Icon: Compass, text: 'Get help when you\'re stuck on something' },
            { Icon: Star, text: 'Brainstorm an AI opportunity for your work' },
            { Icon: Sunrise, text: 'Reflect on your day with a wrap-up' },
          ].map(({ Icon, text }) => (
            <div key={text} className="flex items-center gap-3">
              <Icon
                className="w-4 h-4 shrink-0"
                strokeWidth={1.5}
                style={{ color: 'var(--color-text-muted)' }}
              />
              <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                {text}
              </span>
            </div>
          ))}
        </div>

        <div>
          <button
            onClick={onContinue}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-colors"
            style={{ backgroundColor: 'var(--color-primary)' }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--color-primary-hover)')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'var(--color-primary)')}
          >
            Let's get started
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  // Week 2+: lighter card with weekly feature nudge
  const nudge = WEEKLY_NUDGES[week] ?? WEEKLY_NUDGES[2]!;
  const NudgeIcon = nudge.Icon;

  return (
    <div
      className="my-4 mx-auto w-full rounded-xl border p-6"
      style={{
        backgroundColor: 'var(--color-surface-white)',
        borderColor: 'var(--color-border)',
      }}
    >
      <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
        Ready for Day {week}
      </h3>

      <div className="flex items-start gap-3 mb-4">
        <NudgeIcon
          className="w-4 h-4 shrink-0 mt-0.5"
          strokeWidth={1.5}
          style={{ color: 'var(--color-primary)' }}
        />
        <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
          {nudge.text}
        </p>
      </div>

      <div>
        <button
          onClick={onContinue}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-colors"
          style={{ backgroundColor: 'var(--color-primary)' }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--color-primary-hover)')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'var(--color-primary)')}
        >
          Let's go
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
