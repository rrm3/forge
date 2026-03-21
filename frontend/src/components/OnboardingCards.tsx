/**
 * OnboardingCards - 4-card onboarding sequence in a contained card.
 *
 * Shows BEFORE the intake chat to introduce AI Tuesdays.
 * Each card has a crisp geometric visual, headline, body text,
 * dot indicators, and navigation. Purely presentational.
 */

import { useCallback, useEffect, useState } from 'react';

interface OnboardingCardsProps {
  onComplete: () => void;
  onCardChange?: (cardIndex: number) => void;
}

/* ------------------------------------------------------------------ */
/* Style injection                                                     */
/* ------------------------------------------------------------------ */

const STYLE_ID = 'onboarding-cards-styles';

function ensureStyles() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) return;

  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    @keyframes onb-orbit {
      0% { transform: rotate(0deg) translateX(var(--orbit-r)) rotate(0deg); }
      100% { transform: rotate(360deg) translateX(var(--orbit-r)) rotate(-360deg); }
    }
    @keyframes onb-pulse-ring {
      0% { transform: scale(1); opacity: 0.5; }
      100% { transform: scale(1.4); opacity: 0; }
    }
    @keyframes onb-float {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-6px); }
    }
    @keyframes onb-gradient-rotate {
      from { --onb-angle: 0deg; }
      to   { --onb-angle: 360deg; }
    }
    @property --onb-angle {
      syntax: '<angle>';
      initial-value: 0deg;
      inherits: false;
    }
    @media (prefers-reduced-motion: reduce) {
      .onb-anim { animation: none !important; }
    }
  `;
  document.head.appendChild(style);
}

/* ------------------------------------------------------------------ */
/* Card content                                                        */
/* ------------------------------------------------------------------ */

const CARDS = [
  {
    headline: 'Think, play, learn by doing',
    body: "AI Tuesdays gives you one day a week to explore what AI means for your work. Not a course. Not a checkbox. Time the company is making for you to experiment, get curious, and discover new ways to solve the problems you care about.",
  },
  {
    headline: 'Your AI companion',
    body: "This is your home base for the next 12 weeks. It learns what you're working on, suggests ideas that fit, and helps when you're stuck. Think of it as a knowledgeable colleague who's always available.",
  },
  {
    headline: 'Better together',
    body: "As you discover what works, we'll capture tips and practices you can share with everyone. Later in the program, we want to connect people across functions to work on projects that drive real value.",
  },
  {
    headline: 'A quick conversation to start',
    body: "Before jumping in, it helps to know a bit about you - your role, what you're working on, what you're curious about. Takes about 10 minutes. Speak or type, whatever feels natural.",
  },
];

/* ------------------------------------------------------------------ */
/* Crisp geometric visuals (one per card)                              */
/* ------------------------------------------------------------------ */

const C = { cyan: '#22D3EE', indigo: '#818CF8', purple: '#C084FC', sky: '#38BDF8' };

/** Card 1: Three overlapping gradient circles - crisp, no blur */
function Visual1() {
  return (
    <div className="relative" style={{ width: 160, height: 160 }}>
      <div className="onb-anim absolute rounded-full" style={{
        width: 80, height: 80, left: 10, top: 20,
        background: `linear-gradient(135deg, ${C.cyan}, ${C.sky})`,
        opacity: 0.5,
        animation: 'onb-float 6s ease-in-out infinite',
      }} />
      <div className="onb-anim absolute rounded-full" style={{
        width: 90, height: 90, left: 50, top: 10,
        background: `linear-gradient(135deg, ${C.indigo}, ${C.purple})`,
        opacity: 0.45,
        animation: 'onb-float 7s ease-in-out 1s infinite',
      }} />
      <div className="onb-anim absolute rounded-full" style={{
        width: 70, height: 70, left: 40, top: 60,
        background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
        opacity: 0.5,
        animation: 'onb-float 5.5s ease-in-out 0.5s infinite',
      }} />
    </div>
  );
}

/** Card 2: Central gradient circle with orbiting dots */
function Visual2() {
  const dots = [
    { r: 55, size: 10, color: C.cyan, dur: '5s', delay: '0s' },
    { r: 55, size: 7, color: C.indigo, dur: '5s', delay: '-1.7s' },
    { r: 55, size: 8, color: C.sky, dur: '5s', delay: '-3.3s' },
    { r: 80, size: 6, color: C.purple, dur: '7s', delay: '0s' },
    { r: 80, size: 8, color: C.cyan, dur: '7s', delay: '-3.5s' },
  ];

  return (
    <div className="relative" style={{ width: 160, height: 160 }}>
      {/* Central circle */}
      <div className="absolute rounded-full" style={{
        width: 48, height: 48, left: 56, top: 56,
        background: `conic-gradient(from 45deg, ${C.cyan}, ${C.indigo}, ${C.purple}, ${C.sky}, ${C.cyan})`,
        opacity: 0.7,
        animation: 'onb-gradient-rotate 4s linear infinite',
      }} />
      {/* Orbiting dots */}
      {dots.map((d, i) => (
        <div key={i} className="onb-anim absolute" style={{
          left: 80 - d.size / 2, top: 80 - d.size / 2,
          width: d.size, height: d.size,
          ['--orbit-r' as string]: `${d.r}px`,
          animation: `onb-orbit ${d.dur} linear infinite`,
          animationDelay: d.delay,
        }}>
          <div className="w-full h-full rounded-full" style={{
            background: d.color, opacity: 0.6,
          }} />
        </div>
      ))}
    </div>
  );
}

/** Card 3: Constellation - nodes drift around and lines follow */
function Visual3() {
  const nodes = [
    { cx: 30, cy: 50, r: 6, color: C.cyan, dx: 8, dy: -10, dur: 5 },
    { cx: 80, cy: 25, r: 8, color: C.indigo, dx: -6, dy: 12, dur: 6.5 },
    { cx: 130, cy: 55, r: 7, color: C.purple, dx: 10, dy: 8, dur: 5.5 },
    { cx: 60, cy: 90, r: 9, color: C.sky, dx: -12, dy: -6, dur: 7 },
    { cx: 110, cy: 100, r: 6, color: C.cyan, dx: 6, dy: -14, dur: 6 },
    { cx: 155, cy: 110, r: 5, color: C.indigo, dx: -8, dy: 10, dur: 5.8 },
    { cx: 30, cy: 120, r: 5, color: C.purple, dx: 14, dy: -4, dur: 7.5 },
  ];
  const edges = [[0,1],[1,2],[0,3],[1,4],[2,5],[3,4],[3,6],[4,5]];

  // Each node drifts in an elliptical path using two animate elements (cx + cy)
  return (
    <svg viewBox="0 0 185 140" style={{ width: 185, height: 140, overflow: 'visible' }}>
      {/* Lines connect to animated node positions via <use> won't work, so we animate lines too */}
      {edges.map(([a, b], i) => {
        const na = nodes[a], nb = nodes[b];
        return (
          <line key={i}
            x1={na.cx} y1={na.cy} x2={nb.cx} y2={nb.cy}
            stroke={C.indigo} strokeOpacity={0.15} strokeWidth={1.2}
          >
            <animate attributeName="x1"
              values={`${na.cx};${na.cx + na.dx};${na.cx}`}
              dur={`${na.dur}s`} repeatCount="indefinite" begin={`${a * 0.3}s`}
            />
            <animate attributeName="y1"
              values={`${na.cy};${na.cy + na.dy};${na.cy}`}
              dur={`${na.dur}s`} repeatCount="indefinite" begin={`${a * 0.3}s`}
            />
            <animate attributeName="x2"
              values={`${nb.cx};${nb.cx + nb.dx};${nb.cx}`}
              dur={`${nb.dur}s`} repeatCount="indefinite" begin={`${b * 0.3}s`}
            />
            <animate attributeName="y2"
              values={`${nb.cy};${nb.cy + nb.dy};${nb.cy}`}
              dur={`${nb.dur}s`} repeatCount="indefinite" begin={`${b * 0.3}s`}
            />
          </line>
        );
      })}
      {/* Nodes drift in elliptical paths */}
      {nodes.map((n, i) => (
        <g key={i}>
          <circle cx={n.cx} cy={n.cy} r={n.r} fill={n.color} opacity={0.6}>
            <animate attributeName="cx"
              values={`${n.cx};${n.cx + n.dx};${n.cx}`}
              dur={`${n.dur}s`} repeatCount="indefinite" begin={`${i * 0.3}s`}
            />
            <animate attributeName="cy"
              values={`${n.cy};${n.cy + n.dy};${n.cy}`}
              dur={`${n.dur}s`} repeatCount="indefinite" begin={`${i * 0.3}s`}
            />
          </circle>
          {/* Subtle glow behind larger nodes */}
          {n.r >= 7 && (
            <circle cx={n.cx} cy={n.cy} r={n.r * 2.5} fill={n.color} opacity={0.08}>
              <animate attributeName="cx"
                values={`${n.cx};${n.cx + n.dx};${n.cx}`}
                dur={`${n.dur}s`} repeatCount="indefinite" begin={`${i * 0.3}s`}
              />
              <animate attributeName="cy"
                values={`${n.cy};${n.cy + n.dy};${n.cy}`}
                dur={`${n.dur}s`} repeatCount="indefinite" begin={`${i * 0.3}s`}
              />
            </circle>
          )}
        </g>
      ))}
    </svg>
  );
}

/** Card 4: Mic button preview with pulse rings */
function Visual4() {
  return (
    <div className="relative" style={{ width: 120, height: 120 }}>
      {/* Pulse rings */}
      {[0, 0.7, 1.4].map((delay, i) => (
        <div key={i} className="onb-anim absolute rounded-full" style={{
          width: 64, height: 64, left: 28, top: 28,
          border: `2px solid ${[C.sky, C.indigo, C.purple][i]}`,
          opacity: 0.5,
          animation: `onb-pulse-ring 2s ease-out ${delay}s infinite`,
        }} />
      ))}
      {/* Central gradient circle */}
      <div className="absolute rounded-full" style={{
        width: 48, height: 48, left: 36, top: 36,
        background: `conic-gradient(from 120deg, ${C.cyan}, ${C.indigo}, ${C.purple}, ${C.sky}, ${C.cyan})`,
        animation: 'onb-gradient-rotate 4s linear infinite',
      }} />
    </div>
  );
}

const VISUALS = [Visual1, Visual2, Visual3, Visual4];

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

// Transition phases: idle -> exiting (old slides out) -> entering (new slides in) -> idle
type Phase = 'idle' | 'exiting' | 'entering';

export function OnboardingCards({ onComplete, onCardChange }: OnboardingCardsProps) {
  const [currentCard, setCurrentCard] = useState(0);
  const [direction, setDirection] = useState<'forward' | 'back'>('forward');
  const [phase, setPhase] = useState<Phase>('idle');

  useEffect(() => { ensureStyles(); }, []);

  // Notify parent when card changes (for pre-loading)
  useEffect(() => {
    onCardChange?.(currentCard);
  }, [currentCard, onCardChange]);

  const goForward = useCallback(() => {
    if (phase !== 'idle') return;
    if (currentCard === CARDS.length - 1) { onComplete(); return; }
    setDirection('forward');
    setPhase('exiting');
  }, [currentCard, phase, onComplete]);

  const goBack = useCallback(() => {
    if (phase !== 'idle' || currentCard === 0) return;
    setDirection('back');
    setPhase('exiting');
  }, [currentCard, phase]);

  // Phase 1: exiting done -> swap card + start entering
  useEffect(() => {
    if (phase !== 'exiting') return;
    const timer = setTimeout(() => {
      setCurrentCard((prev) => direction === 'forward' ? prev + 1 : prev - 1);
      setPhase('entering');
    }, 200);
    return () => clearTimeout(timer);
  }, [phase, direction]);

  // Phase 2: entering done -> idle
  useEffect(() => {
    if (phase !== 'entering') return;
    const timer = setTimeout(() => setPhase('idle'), 200);
    return () => clearTimeout(timer);
  }, [phase]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'ArrowRight') goForward();
      else if (e.key === 'ArrowLeft') goBack();
      else if (e.key === 'Enter' && currentCard === CARDS.length - 1) onComplete();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [currentCard, goForward, goBack, onComplete]);

  const card = CARDS[currentCard];
  const Visual = VISUALS[currentCard];
  const isLast = currentCard === CARDS.length - 1;

  // Apple-style directional slide:
  // Forward: exit slides left, enter slides in from right
  // Back: exit slides right, enter slides in from left
  const fwd = direction === 'forward';
  const fadeStyle: React.CSSProperties =
    phase === 'exiting'
      ? { transition: 'opacity 200ms ease-in, transform 200ms ease-in',
          opacity: 0, transform: `translateX(${fwd ? '-30px' : '30px'})` }
    : phase === 'entering'
      ? { transition: 'none', opacity: 0, transform: `translateX(${fwd ? '30px' : '-30px'})` }
    : { transition: 'opacity 200ms ease-out, transform 200ms ease-out',
        opacity: 1, transform: 'translateX(0)' };

  // Entering needs a frame to pick up the start position, then animate to final
  // We use a ref trick: set initial position with no transition, then next frame add transition
  const [enterReady, setEnterReady] = useState(false);
  useEffect(() => {
    if (phase === 'entering') {
      // Wait one frame then trigger the animate-in
      requestAnimationFrame(() => setEnterReady(true));
    } else {
      setEnterReady(false);
    }
  }, [phase]);

  const actualStyle: React.CSSProperties = (phase === 'entering' && enterReady)
    ? { transition: 'opacity 200ms ease-out, transform 200ms ease-out',
        opacity: 1, transform: 'translateX(0)' }
    : fadeStyle;

  return (
    <div
      className="flex-1 flex items-center justify-center px-4 py-8"
      style={{ backgroundColor: 'var(--color-surface, #FAFBFC)' }}
    >
      {/* Card container - fixed height so navigation doesn't jump */}
      <div
        className="w-full max-w-md rounded-2xl px-8 py-10 md:px-10 md:py-12 flex flex-col"
        style={{
          backgroundColor: 'var(--color-surface-white, #FFFFFF)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04), 0 4px 20px rgba(0,0,0,0.03)',
          minHeight: '420px',
          maxHeight: '520px',
          height: '70vh',
        }}
      >
        {/* Visual - fixed height zone */}
        <div className="flex justify-center items-center shrink-0" style={{ ...actualStyle, height: '160px' }} aria-hidden="true">
          <Visual />
        </div>

        {/* Text - fills remaining space, content top-aligned */}
        <div className="flex-1 text-center mt-4" style={actualStyle}>
          <h2 style={{
            color: 'var(--color-text-primary, #1A1F25)',
            fontFamily: "'Satoshi', system-ui, sans-serif",
            fontWeight: 700,
            fontSize: '22px',
            lineHeight: 1.3,
            marginBottom: '12px',
          }}>
            {card.headline}
          </h2>
          <p style={{
            color: 'var(--color-text-secondary, #4A5568)',
            fontFamily: "'Inter', system-ui, sans-serif",
            fontWeight: 400,
            fontSize: '15px',
            lineHeight: 1.7,
          }}>
            {card.body}
          </p>

        </div>

        {/* Navigation - pinned to bottom of card */}
        <div className="mt-auto pt-6 shrink-0" style={{ opacity: phase !== 'idle' ? 0.5 : 1, transition: 'opacity 200ms ease-out' }}>
          <div className="flex items-center justify-between">
            <button
              onClick={goBack}
              className="text-sm font-medium px-4 py-2 rounded-full transition-colors"
              style={{
                color: '#64748B',
                visibility: currentCard === 0 ? 'hidden' : 'visible',
                fontFamily: "'Inter', system-ui, sans-serif",
                fontWeight: 500,
              }}
            >
              &larr; Back
            </button>
            <div className="flex gap-2">
              {CARDS.map((_, i) => (
                <div key={i} className="rounded-full" style={{
                  width: 7, height: 7,
                  backgroundColor: i === currentCard ? '#159AC9' : '#E2E8F0',
                  transition: 'background-color 300ms',
                }} />
              ))}
            </div>
            <button
              onClick={isLast ? onComplete : goForward}
              className="text-sm font-medium px-5 py-2 rounded-full text-white transition-colors"
              style={{
                backgroundColor: '#159AC9',
                fontFamily: "'Inter', system-ui, sans-serif",
                fontWeight: 500,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#1287B3'; }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#159AC9'; }}
            >
              {isLast ? "Let's go \u2192" : 'Next \u2192'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
