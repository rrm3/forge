import { useEffect, useRef, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSession } from '../state/SessionContext';
import { MessageBubble } from './MessageBubble';

const SUGGESTIONS = [
  'Get started with AI',
  'Review my progress',
  'Journal what I learned today',
  'Browse project ideas',
];

function EmptyState({ onSuggestion }: { onSuggestion: (text: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 text-center">
      <div className="mb-6">
        <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center mx-auto mb-4">
          <svg className="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Welcome to AI Tuesdays</h2>
        <p className="mt-2 text-sm text-gray-500 max-w-sm">
          Your AI companion for the Forge program. Ask questions, reflect on your learning, and explore ideas.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2 w-full max-w-md">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onSuggestion(s)}
            className="px-3 py-2.5 rounded-xl border border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50 text-sm text-gray-700 hover:text-blue-700 transition-colors text-left"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

interface AutoTextareaProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
}

function AutoTextarea({ value, onChange, onSend, disabled }: AutoTextareaProps) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 144)}px`;
  }, [value]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) onSend();
    }
  }

  return (
    <textarea
      ref={ref}
      rows={1}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={handleKeyDown}
      disabled={disabled}
      placeholder="Ask anything..."
      className="flex-1 resize-none bg-transparent outline-none text-sm text-gray-800 placeholder-gray-400 py-2.5 leading-relaxed w-full"
      style={{ minHeight: '40px' }}
    />
  );
}

export function ChatView() {
  const { state, sendChatMessage, cancelStreaming, newSession } = useSession();
  const { messages, isStreaming, streamingText, activeSessionId } = state;

  const [inputValue, setInputValue] = useState('');
  const inputValueRef = useRef(inputValue);
  const bottomRef = useRef<HTMLDivElement>(null);

  function handleInputChange(v: string) {
    inputValueRef.current = v;
    setInputValue(v);
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, streamingText]);

  const handleSend = useCallback(async () => {
    const text = inputValueRef.current.trim();
    if (!text || isStreaming) return;

    if (!activeSessionId) {
      await newSession();
    }

    handleInputChange('');
    sendChatMessage(text);
  }, [isStreaming, activeSessionId, newSession, sendChatMessage]);

  const handleSuggestion = useCallback(async (text: string) => {
    if (!activeSessionId) {
      await newSession();
    }
    sendChatMessage(text);
  }, [activeSessionId, newSession, sendChatMessage]);

  const hasMessages = messages.length > 0 || isStreaming;

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto py-4 space-y-1">
        {!hasMessages ? (
          <EmptyState onSuggestion={handleSuggestion} />
        ) : (
          <>
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}

            {/* Streaming assistant text */}
            {isStreaming && streamingText && (
              <div className="flex justify-start px-4 py-1">
                <div className="max-w-xl bg-white border border-gray-200 px-4 py-3 rounded-2xl rounded-bl-md text-sm leading-relaxed text-gray-800 shadow-sm prose prose-sm max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingText}</ReactMarkdown>
                  <span className="inline-block w-1.5 h-4 bg-blue-500 ml-0.5 animate-pulse rounded-sm align-middle" />
                </div>
              </div>
            )}

            {/* Thinking indicator when streaming but no text yet */}
            {isStreaming && !streamingText && (
              <div className="flex justify-start px-4 py-1">
                <div className="bg-white border border-gray-200 px-4 py-3 rounded-2xl rounded-bl-md shadow-sm">
                  <div className="flex gap-1 items-center">
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="px-4 pb-4 pt-2">
        <div className="flex items-end gap-2 bg-white border border-gray-200 rounded-2xl px-3 shadow-sm focus-within:border-blue-400 focus-within:ring-1 focus-within:ring-blue-400 transition-all">
          <AutoTextarea
            value={inputValue}
            onChange={handleInputChange}
            onSend={handleSend}
            disabled={isStreaming}
          />

          <div className="pb-2 shrink-0">
            {isStreaming ? (
              <button
                onClick={cancelStreaming}
                className="flex items-center justify-center w-8 h-8 rounded-xl bg-red-500 hover:bg-red-600 text-white transition-colors"
                title="Cancel"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="1" />
                </svg>
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!inputValue.trim()}
                className="flex items-center justify-center w-8 h-8 rounded-xl bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                title="Send"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            )}
          </div>
        </div>
        <p className="text-xs text-center text-gray-400 mt-1.5">
          Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
