import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message } from '../api/types';

interface CodeBlockProps {
  children?: React.ReactNode;
  className?: string;
}

function CodeBlock({ children, className }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const isBlock = className?.startsWith('language-') ?? false;

  if (!isBlock) {
    return (
      <code className="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono">
        {children}
      </code>
    );
  }

  const text = typeof children === 'string' ? children : String(children ?? '');

  function handleCopy() {
    navigator.clipboard.writeText(text.trimEnd()).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="relative group my-3">
      <pre className="bg-gray-800 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm font-mono">
        <code>{children}</code>
      </pre>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
      >
        {copied ? 'Copied!' : 'Copy'}
      </button>
    </div>
  );
}

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const [expanded, setExpanded] = useState(false);

  if (message.role === 'tool_call') {
    const name = message.tool_name || message.content;
    return (
      <div className="flex justify-start px-4 py-0.5">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gray-100 text-gray-500 text-xs">
          <svg className="w-3 h-3 animate-spin text-gray-400" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          Using {name}...
        </div>
      </div>
    );
  }

  if (message.role === 'tool_result') {
    const lines = message.content.split('\n');
    const preview = lines.slice(0, 2).join('\n');
    const hasMore = lines.length > 2;

    return (
      <div className="flex justify-start px-4 py-0.5">
        <div className="max-w-xl bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-600 font-mono">
          <pre className="whitespace-pre-wrap break-words">{expanded ? message.content : preview}</pre>
          {hasMore && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-1 text-blue-600 hover:text-blue-700 font-sans"
            >
              {expanded ? 'Show less' : `Show ${lines.length - 2} more lines`}
            </button>
          )}
        </div>
      </div>
    );
  }

  if (message.role === 'user') {
    return (
      <div className="flex justify-end px-4 py-1">
        <div className="max-w-xl bg-blue-600 text-white px-4 py-2.5 rounded-2xl rounded-br-md text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  // assistant
  return (
    <div className="flex justify-start px-4 py-1">
      <div className="max-w-xl bg-white border border-gray-200 px-4 py-3 rounded-2xl rounded-bl-md text-sm leading-relaxed text-gray-800 shadow-sm prose prose-sm max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code: ({ className, children }) => (
              <CodeBlock className={className}>{children}</CodeBlock>
            ),
          }}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
