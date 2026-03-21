/**
 * IntakeView - Full-screen focused layout for first-run intake.
 *
 * Blocks access to everything else until intake is complete.
 * No sidebar, no action buttons, no session history.
 * Centered chat with warm welcome header and voice toggle.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { Mic, Send, Square } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSession } from '../state/SessionContext';
import { MessageBubble, streamingMarkdownComponents } from './MessageBubble';
import { VoiceMode } from './VoiceMode';

export function IntakeView() {
  const { state, sendChatMessage, startTypedSession, cancelStreaming } = useSession();
  const { messages = [], isStreaming, streamingText, activeSessionId } = state;

  const [inputValue, setInputValue] = useState('');
  const [voiceActive, setVoiceActive] = useState(false);
  const inputValueRef = useRef(inputValue);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const intakeStarted = useRef(false);

  // Auto-start intake session
  useEffect(() => {
    if (intakeStarted.current) return;
    if (!state.sessionsLoaded) return;

    intakeStarted.current = true;
    startTypedSession('intake');
  }, [state.sessionsLoaded, startTypedSession]);

  function handleInputChange(v: string) {
    inputValueRef.current = v;
    setInputValue(v);
  }

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 184)}px`;
  }, [inputValue]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, streamingText]);

  const handleSend = useCallback(() => {
    const text = inputValueRef.current.trim();
    if (!text || isStreaming) return;
    handleInputChange('');
    sendChatMessage(text);
  }, [isStreaming, sendChatMessage]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim() && !isStreaming) handleSend();
    }
  }

  const hasInput = inputValue.trim().length > 0;

  // Voice mode
  if (voiceActive && activeSessionId) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: 'var(--color-surface)' }}>
        <VoiceMode
          sessionId={activeSessionId}
          sessionType="intake"
          onExit={() => setVoiceActive(false)}
        />
      </div>
    );
  }

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: 'var(--color-surface)' }}
    >
      {/* Welcome header */}
      <div className="text-center pt-12 pb-6 px-6">
        <h1 className="text-3xl font-bold tracking-tight" style={{ color: 'var(--color-text-primary)' }}>
          Welcome to AI Tuesdays
        </h1>
        <p className="mt-2 text-base" style={{ color: 'var(--color-text-muted)' }}>
          Let's get to know each other.
        </p>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-4 py-4 space-y-1">
          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}

          {isStreaming && streamingText && (
            <div className="flex justify-start py-1">
              <div className="max-w-[95%] md:max-w-[85%] prose prose-sm max-w-none" style={{ color: 'var(--color-text-primary)' }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={streamingMarkdownComponents}>
                  {streamingText}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {isStreaming && (
            <div className="flex justify-start py-1">
              <div className="px-1 py-1">
                <div className="flex gap-1.5 items-center">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: 'var(--color-text-placeholder)', animation: 'bounce 1.4s ease-in-out infinite' }} />
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: 'var(--color-text-placeholder)', animation: 'bounce 1.4s ease-in-out 0.2s infinite' }} />
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: 'var(--color-text-placeholder)', animation: 'bounce 1.4s ease-in-out 0.4s infinite' }} />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="mx-auto max-w-2xl w-full px-4 pb-4">
        <div
          className="relative rounded-xl border transition-all duration-200"
          style={{
            backgroundColor: 'var(--color-surface-white)',
            borderColor: 'var(--color-border)',
          }}
        >
          <div className="p-2">
            <textarea
              ref={textareaRef}
              rows={1}
              value={inputValue}
              onChange={(e) => handleInputChange(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              placeholder="Type your response..."
              className="w-full resize-none bg-transparent outline-none border-none text-base md:text-sm leading-6 p-1 pb-8 pr-20 overflow-y-auto"
              style={{
                color: 'var(--color-text-primary)',
                minHeight: '40px',
                maxHeight: '184px',
              }}
              aria-label="Intake response"
            />

            <div className="absolute bottom-0 right-0 flex items-center gap-1.5 pb-2 pr-2">
              {/* Voice toggle */}
              {!isStreaming && activeSessionId && (
                <button
                  onClick={() => setVoiceActive(true)}
                  className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors duration-150"
                  style={{ color: 'var(--color-text-muted)' }}
                  title="Switch to voice"
                  aria-label="Switch to voice mode"
                >
                  <Mic className="w-4 h-4" strokeWidth={1.5} />
                </button>
              )}

              {isStreaming ? (
                <button
                  onClick={cancelStreaming}
                  className="flex items-center justify-center w-8 h-8 rounded-lg text-white transition-colors duration-150"
                  style={{ backgroundColor: 'var(--color-text-secondary)' }}
                  title="Stop"
                >
                  <Square className="w-4 h-4" fill="currentColor" strokeWidth={0} />
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!hasInput}
                  className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors duration-150"
                  style={{
                    backgroundColor: hasInput ? 'var(--color-primary)' : 'transparent',
                    color: hasInput ? '#FFFFFF' : 'var(--color-text-placeholder)',
                  }}
                  title="Send"
                >
                  <Send className="w-4 h-4" strokeWidth={1.5} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Need help link */}
      <div className="text-center pb-4">
        <a
          href="mailto:forge-support@digitalscience.com"
          className="text-xs hover:underline"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Need help?
        </a>
      </div>
    </div>
  );
}
