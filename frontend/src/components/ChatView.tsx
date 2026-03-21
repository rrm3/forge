import { useEffect, useRef, useState, useCallback } from 'react';
import { Send, Square, Mic } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { VoiceMode } from './VoiceMode';
import remarkGfm from 'remark-gfm';
import { useSession } from '../state/SessionContext';
import { MessageBubble, streamingMarkdownComponents } from './MessageBubble';

export function ChatView() {
  const { state, sendChatMessage, cancelStreaming } = useSession();
  const { messages = [], isStreaming, streamingText, connectionStatus } = state;

  const [inputValue, setInputValue] = useState('');
  const [voiceActive, setVoiceActive] = useState(false);
  const inputValueRef = useRef(inputValue);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  function handleInputChange(v: string) {
    inputValueRef.current = v;
    setInputValue(v);
  }

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 184)}px`;
  }, [inputValue]);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, streamingText]);

  // Focus input when session loads
  useEffect(() => {
    textareaRef.current?.focus();
  }, [state.activeSessionId]);

  const handleSend = useCallback(async () => {
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

  const hasMessages = messages.length > 0 || isStreaming;
  const hasInput = inputValue.trim().length > 0;
  const isReconnecting = connectionStatus === 'reconnecting' || connectionStatus === 'disconnected';

  // Voice mode
  if (voiceActive && state.activeSessionId) {
    return (
      <VoiceMode
        sessionId={state.activeSessionId}
        onExit={() => setVoiceActive(false)}
      />
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
      {/* Reconnecting banner */}
      {isReconnecting && (
        <div
          className="px-4 py-1.5 text-center border-b"
          style={{
            backgroundColor: '#FFFBEB',
            borderColor: '#FDE68A',
          }}
          role="status"
          aria-live="polite"
        >
          <span className="text-sm" style={{ color: '#92400E' }}>
            Reconnecting...
            <span
              className="inline-block w-1.5 h-1.5 rounded-full ml-2"
              style={{ backgroundColor: '#F59E0B', animation: 'pulse 1.5s ease-in-out infinite' }}
            />
          </span>
        </div>
      )}

      {/* ARIA live region for status changes */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {isStreaming ? 'AI is responding...' : ''}
        {isReconnecting ? 'Connection lost. Reconnecting...' : ''}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {!hasMessages ? (
          <div className="flex flex-col items-center justify-center h-full px-6 text-center">
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              Send a message to start the conversation.
            </p>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl px-4 py-4 space-y-1">
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}

            {/* Streaming assistant text */}
            {isStreaming && streamingText && (
              <div className="flex justify-start py-1">
                <div className="max-w-[95%] md:max-w-[85%] prose prose-sm max-w-none" style={{ color: 'var(--color-text-primary)' }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={streamingMarkdownComponents}>
                    {streamingText}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {/* Streaming dots indicator */}
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

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="mx-auto max-w-3xl w-full px-0 md:px-4 pb-0 md:pb-4">
        <div
          className="relative rounded-none md:rounded-xl border-0 border-t md:border transition-all duration-200"
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
              placeholder="Ask anything..."
              className="w-full resize-none bg-transparent outline-none border-none text-base md:text-sm leading-6 p-1 pb-8 pr-14 overflow-y-auto"
              style={{
                color: 'var(--color-text-primary)',
                minHeight: '40px',
                maxHeight: '184px',
                caretColor: 'var(--color-text-primary)',
              }}
              aria-label="Message input"
            />

            {/* Action buttons - bottom right */}
            <div className="absolute bottom-0 right-0 flex items-center gap-1.5 pb-2 pr-2">
              {/* Voice toggle */}
              {!isStreaming && state.activeSessionId && (
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
                    backgroundColor: hasInput ? 'var(--color-primary)' : 'transparent',
                    color: hasInput ? '#FFFFFF' : 'var(--color-text-placeholder)',
                    cursor: hasInput ? 'pointer' : 'default',
                  }}
                  title="Send"
                  aria-label="Send message"
                >
                  <Send className="w-4 h-4" strokeWidth={1.5} />
                </button>
              )}
            </div>
          </div>
        </div>
        <p className="text-xs text-center mt-1.5 pb-1 hidden md:block" style={{ color: 'var(--color-text-placeholder)' }}>
          Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
