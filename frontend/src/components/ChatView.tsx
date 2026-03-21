import { useEffect, useRef, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSession } from '../state/SessionContext';
import { MessageBubble, streamingMarkdownComponents } from './MessageBubble';

export function ChatView() {
  const { state, sendChatMessage, cancelStreaming, deselectSession } = useSession();
  const { messages = [], isStreaming, streamingText, activeSessionId, connectionStatus } = state;

  const [inputValue, setInputValue] = useState('');
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

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Reconnecting banner */}
      {isReconnecting && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-center">
          <span className="text-sm text-amber-700">
            Reconnecting...
            <span className="inline-block w-1.5 h-1.5 bg-amber-500 rounded-full ml-2" style={{ animation: 'pulse 1.5s ease-in-out infinite' }} />
          </span>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {!hasMessages ? (
          <div className="flex flex-col items-center justify-center h-full px-6 text-center">
            <div className="mb-6">
              <div className="w-12 h-12 rounded-full bg-[#f3f6f7] flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-[#93A6B0]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h2 className="text-lg font-medium text-[#21262E]">Start a conversation</h2>
              <p className="mt-2 text-sm text-[#5e7a88] max-w-sm">
                Type a message below or use the action buttons on the home screen.
              </p>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl px-4 py-4 space-y-1">
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}

            {/* Streaming assistant text */}
            {isStreaming && streamingText && (
              <div className="flex justify-start py-1">
                <div className="max-w-[95%] md:max-w-[85%] prose prose-sm max-w-none text-[var(--color-text-primary)]">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={streamingMarkdownComponents}>
                    {streamingText}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {/* Thinking/streaming indicator */}
            {isStreaming && (
              <div className="flex justify-start py-1">
                <div className="px-1 py-1">
                  <div className="flex gap-1.5 items-center">
                    <span className="w-2 h-2 bg-[#93A6B0] rounded-full" style={{ animation: 'bounce 1.4s ease-in-out infinite' }} />
                    <span className="w-2 h-2 bg-[#93A6B0] rounded-full" style={{ animation: 'bounce 1.4s ease-in-out 0.2s infinite' }} />
                    <span className="w-2 h-2 bg-[#93A6B0] rounded-full" style={{ animation: 'bounce 1.4s ease-in-out 0.4s infinite' }} />
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
        <div className="relative bg-white rounded-none border-0 border-t border-gray-300 md:rounded-xl md:border md:border-gray-300 transition-all duration-300 ease-in-out">
          <div className="p-2">
            <textarea
              ref={textareaRef}
              rows={1}
              value={inputValue}
              onChange={(e) => handleInputChange(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              placeholder="Ask anything..."
              className="w-full resize-none bg-transparent outline-none border-none text-base md:text-sm text-[#21262E] placeholder-[#93A6B0] leading-6 p-1 pb-8 pr-2 overflow-y-auto caret-gray-900"
              style={{ minHeight: '40px', maxHeight: '184px' }}
            />

            {/* Buttons - positioned bottom-right */}
            <div className="absolute bottom-0 right-0 flex items-center gap-2 pb-2 pr-2">
              {isStreaming ? (
                <button
                  onClick={cancelStreaming}
                  className="flex items-center justify-center w-8 h-8 rounded-lg bg-[#4b5563] hover:bg-[#374151] text-white transition-colors duration-150"
                  title="Stop"
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="6" y="6" width="12" height="12" rx="1" />
                  </svg>
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!hasInput}
                  className={`flex items-center justify-center w-8 h-8 rounded-lg transition-colors duration-150 ${
                    hasInput
                      ? 'bg-[#4b5563] hover:bg-[#374151] text-white'
                      : 'bg-transparent text-[#93A6B0] cursor-default'
                  }`}
                  title="Send"
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 256 256">
                    <path d="M231.4,44.34s0,.1,0,.15l-58.2,191.94a15.88,15.88,0,0,1-14,11.51q-.69.06-1.38.06a15.86,15.86,0,0,1-14.42-9.15l-35.71-75.39,41.67-41.67a8,8,0,0,0-11.32-11.32l-41.67,41.67L21.13,115.78A16,16,0,0,1,23.5,87.72L215.44,29.52a16,16,0,0,1,16,3.82Z" />
                  </svg>
                </button>
              )}
            </div>
          </div>
        </div>
        <p className="text-xs text-center text-[#93A6B0] mt-1.5 pb-1 hidden md:block">
          Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
