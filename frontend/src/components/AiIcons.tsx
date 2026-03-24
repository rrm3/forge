/**
 * Gemini and Claude brand icons as img components.
 * Source PNGs live in public/ for direct URL reference.
 */

interface AiIconProps {
  size?: number;
  className?: string;
}

export function GeminiIcon({ size = 16, className }: AiIconProps) {
  return (
    <img
      src="/gemini-icon.png"
      alt="Gemini"
      width={size}
      height={size}
      className={className}
      style={{ display: 'inline-block', verticalAlign: 'middle' }}
    />
  );
}

export function ClaudeIcon({ size = 16, className }: AiIconProps) {
  return (
    <img
      src="/claude-icon.png"
      alt="Claude"
      width={size}
      height={size}
      className={className}
      style={{ display: 'inline-block', verticalAlign: 'middle' }}
    />
  );
}
