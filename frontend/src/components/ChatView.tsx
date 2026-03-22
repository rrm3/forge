import { useEffect, useRef, useState, useCallback } from 'react';
import { Square, Send, Check, Bold, Italic, List, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSession } from '../state/SessionContext';
import { useAdminStore } from '../state/adminStore';
import { MessageBubble, streamingMarkdownComponents } from './MessageBubble';
import { VoiceButton } from './VoiceButton';
import { TipPreviewCard } from './TipPreviewCard';
import { IdeaPreviewCard } from './IdeaPreviewCard';

const TOOL_ROLES = new Set(['tool_call', 'tool_result']);

interface ChatViewProps {
  onShowTips?: () => void;
}

export function ChatView({ onShowTips }: ChatViewProps) {
  const adminMode = useAdminStore((s) => s.adminMode);
  const { state, dispatch, sendChatMessage, cancelStreaming } = useSession();
  const { messages = [], isStreaming, streamingText, connectionStatus } = state;

  const [inputValue, setInputValue] = useState('');
  const [isVoiceRecording, setIsVoiceRecording] = useState(false);
  const inputValueRef = useRef(inputValue);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Track how many messages have been sent this session
  const sendCountRef = useRef(0);

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

  // Auto-resize textarea
  useEffect(() => {
    if (isVoiceRecording) return; // Don't resize while recording
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
    sendCountRef.current += 1;
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

  // Hint text
  const showVoiceHint = sendCountRef.current < 3;
  const hintText = isVoiceRecording
    ? 'Recording... tap check to stop'
    : showVoiceHint
      ? 'Tap mic or press CapsLock to respond'
      : 'Enter to send, Shift+Enter for new line';

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
      {/* Reconnecting banner */}
      {isReconnecting && (
        <div
          className="px-4 py-1.5 text-center border-b"
          style={{ backgroundColor: '#FFFBEB', borderColor: '#FDE68A' }}
          role="status"
          aria-live="polite"
        >
          <span className="text-sm" style={{ color: '#92400E' }}>
            Reconnecting...
            <span className="inline-block w-1.5 h-1.5 rounded-full ml-2"
              style={{ backgroundColor: '#F59E0B', animation: 'pulse 1.5s ease-in-out infinite' }} />
          </span>
        </div>
      )}

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
            {messages.filter((msg) => adminMode || !TOOL_ROLES.has(msg.role)).map((msg, i) => (
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

            {/* Tip preview card (editable) or published confirmation */}
            {state.tipReady && !isStreaming && !state.tipPublished && (
              <TipPreviewCard
                initial={state.tipReady}
                onPublished={() => {
                  dispatch({ type: 'SET_TIP_PUBLISHED' });
                }}
                onShowTips={onShowTips}
              />
            )}

            {state.tipPublished && (
              <div
                className="my-4 mx-auto max-w-[95%] md:max-w-[85%] rounded-xl border p-5"
                style={{ backgroundColor: 'var(--color-surface-white)', borderColor: 'var(--color-border)' }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Check className="w-4 h-4" style={{ color: '#059669' }} strokeWidth={2} />
                  <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Tip published!
                  </span>
                </div>
                {onShowTips && (
                  <button
                    onClick={onShowTips}
                    className="text-sm font-medium"
                    style={{ color: 'var(--color-primary)' }}
                  >
                    Browse Tips &rarr;
                  </button>
                )}
              </div>
            )}

            {state.ideaReady && !isStreaming && (
              <IdeaPreviewCard
                initial={state.ideaReady}
                sessionId={state.activeSessionId || ''}
                onSaved={() => dispatch({ type: 'SET_IDEA_READY', idea: null })}
                onSkip={() => dispatch({ type: 'SET_IDEA_READY', idea: null })}
              />
            )}

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="mx-auto max-w-3xl w-full px-0 md:px-4 pb-0 md:pb-4">
        <div className="flex items-end gap-2 px-2 md:px-0">
          {/* Input box with mic inside */}
          <div
            className="relative flex-1 rounded-none md:rounded-xl border-0 border-t md:border transition-all duration-200"
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
                aria-label="Message input"
              />

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
        </div>
        <p className="text-xs text-center mt-1.5 pb-1 hidden md:block" style={{ color: 'var(--color-text-placeholder)' }}>
          {hintText}
        </p>
      </div>
    </div>
  );
}
