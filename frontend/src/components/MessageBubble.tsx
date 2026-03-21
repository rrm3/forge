import { useState, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { Message } from '../api/types';

const LANG_NAMES: Record<string, string> = {
  js: 'JavaScript', jsx: 'JSX', ts: 'TypeScript', tsx: 'TypeScript (React)',
  py: 'Python', rb: 'Ruby', go: 'Go', rs: 'Rust', java: 'Java',
  kt: 'Kotlin', cs: 'C#', cpp: 'C++', c: 'C', sh: 'Shell',
  bash: 'Bash', zsh: 'Zsh', sql: 'SQL', html: 'HTML', css: 'CSS',
  scss: 'SCSS', less: 'Less', json: 'JSON', yaml: 'YAML', yml: 'YAML',
  md: 'Markdown', xml: 'XML', toml: 'TOML', ini: 'INI',
  dockerfile: 'Dockerfile', docker: 'Docker', makefile: 'Makefile',
  terraform: 'Terraform', hcl: 'HCL', swift: 'Swift', r: 'R',
  php: 'PHP', perl: 'Perl', lua: 'Lua', graphql: 'GraphQL',
  proto: 'Protobuf', prisma: 'Prisma', vue: 'Vue', svelte: 'Svelte',
};

function getLangName(lang: string): string {
  return LANG_NAMES[lang.toLowerCase()] || lang.toUpperCase();
}

function CodeBlock({ children, className }: { children?: ReactNode; className?: string }) {
  const [copied, setCopied] = useState(false);
  const lang = className?.replace('language-', '') || '';
  const hasNewlines = typeof children === 'string' && children.includes('\n');
  const isBlock = !!lang || hasNewlines;

  if (!isBlock) {
    return (
      <code className="bg-[var(--color-bg-light)] text-[var(--color-text-secondary)] px-1.5 py-0.5 rounded text-sm font-mono">
        {children}
      </code>
    );
  }

  const text = typeof children === 'string' ? children.replace(/\n$/, '') : String(children ?? '').replace(/\n$/, '');

  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="mb-3 overflow-x-auto rounded-lg border border-[var(--color-border-default)]">
      <div className="flex items-center justify-between px-3 py-2 bg-[var(--color-bg-light)] border-b border-[var(--color-border-default)]">
        <span className="text-xs font-semibold text-[var(--color-text-secondary)]">{lang ? getLangName(lang) : 'Code'}</span>
        <button
          onClick={handleCopy}
          className="text-xs flex items-center gap-1 text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <SyntaxHighlighter
        language={lang || 'text'}
        style={oneDark}
        customStyle={{ margin: 0, padding: '1rem', fontSize: '0.875rem', background: '#1D1F21' }}
        codeTagProps={{ style: { background: 'transparent' } }}
        PreTag="div"
      >
        {text}
      </SyntaxHighlighter>
    </div>
  );
}

// Markdown component overrides matching Acumentum
const markdownComponents = {
  h1: ({ children }: { children?: ReactNode }) => (
    <h1 className="text-2xl font-bold mt-6 mb-4 text-[var(--color-text-primary)]">{children}</h1>
  ),
  h2: ({ children }: { children?: ReactNode }) => (
    <h2 className="text-xl font-bold mt-5 mb-3 text-[var(--color-text-primary)]">{children}</h2>
  ),
  h3: ({ children }: { children?: ReactNode }) => (
    <h3 className="text-lg font-bold mt-4 mb-2 text-[var(--color-text-primary)]">{children}</h3>
  ),
  p: ({ children }: { children?: ReactNode }) => (
    <p className="text-sm leading-relaxed mb-2 text-[var(--color-text-primary)]">{children}</p>
  ),
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="list-disc pl-5 mb-3 text-sm text-[var(--color-text-primary)]">{children}</ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="list-decimal pl-5 mb-3 text-sm text-[var(--color-text-primary)]">{children}</ol>
  ),
  li: ({ children }: { children?: ReactNode }) => (
    <li className="mb-1">{children}</li>
  ),
  a: ({ href, children }: { href?: string; children?: ReactNode }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-[var(--color-text-link,#37738D)] hover:underline">
      {children}
    </a>
  ),
  blockquote: ({ children }: { children?: ReactNode }) => (
    <blockquote className="border-l-4 border-[var(--color-active-blue)] pl-4 italic text-[var(--color-text-secondary)] mb-3">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-[var(--color-border-default)] my-4" />,
  table: ({ children }: { children?: ReactNode }) => (
    <div className="overflow-x-auto mb-3">
      <table className="border-collapse w-full">{children}</table>
    </div>
  ),
  th: ({ children }: { children?: ReactNode }) => (
    <th className="border border-[var(--color-border-default)] bg-[var(--color-bg-light)] px-3 py-2 text-left text-sm font-semibold">
      {children}
    </th>
  ),
  td: ({ children }: { children?: ReactNode }) => (
    <td className="border border-[var(--color-border-default)] px-3 py-2 text-sm">{children}</td>
  ),
  code: ({ className, children }: { className?: string; children?: ReactNode }) => (
    <CodeBlock className={className}>{children}</CodeBlock>
  ),
  pre: ({ children }: { children?: ReactNode }) => <>{children}</>,
};

// Simplified components for streaming (no syntax highlighting to avoid flicker)
export const streamingMarkdownComponents = {
  ...markdownComponents,
  code: ({ children }: { children?: ReactNode }) => (
    <code className="bg-[var(--color-bg-light)] text-[var(--color-text-secondary)] px-1.5 py-0.5 rounded text-sm font-mono">{children}</code>
  ),
  pre: ({ children }: { children?: ReactNode }) => (
    <pre className="bg-[#1D1F21] text-[#C5C8C6] rounded-lg p-4 overflow-x-auto text-sm font-mono leading-relaxed mb-3">{children}</pre>
  ),
};

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const [expanded, setExpanded] = useState(false);

  if (message.role === 'tool_call') {
    const name = message.tool_name || message.content;
    return (
      <div className="flex justify-start py-0.5">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--color-bg-light)] text-[var(--color-text-muted)] text-xs">
          <svg className="w-3 h-3 text-[var(--color-text-placeholder)]" fill="none" viewBox="0 0 24 24" style={{ animation: 'spin 1s linear infinite' }}>
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
      <div className="flex justify-start py-0.5">
        <div className="max-w-[85%] bg-[var(--color-bg-light)] border border-[var(--color-border-light)] rounded-lg px-3 py-2 text-xs text-[var(--color-text-muted)] font-mono">
          <pre className="whitespace-pre-wrap break-words">{expanded ? message.content : preview}</pre>
          {hasMore && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-1 text-[var(--color-active-blue)] hover:opacity-80 font-sans"
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
      <div className="flex justify-end py-1">
        <div className="max-w-[80%] bg-[var(--color-user-bubble)] text-[var(--color-text-primary)] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap break-words">
          {message.content}
        </div>
      </div>
    );
  }

  // assistant
  return (
    <div className="flex justify-start py-1">
      <div
        className="max-w-[95%] md:max-w-[85%] prose prose-sm max-w-none px-4 py-3 rounded-2xl"
        style={{
          backgroundColor: 'var(--color-surface-white, #FFFFFF)',
          color: 'var(--color-text-primary)',
          border: '1px solid var(--color-border, #E2E8F0)',
        }}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={markdownComponents}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
