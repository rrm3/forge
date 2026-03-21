/**
 * Voice Orb - the singular expressive element in an otherwise restrained UI.
 *
 * Uses conic-gradient rotation via CSS for multi-color flowing animation.
 * Audio-reactive behavior driven by Web Audio API AnalyserNode.
 *
 * States: idle, listening, speaking, tool_call, reconnecting
 */

import { useEffect, useRef, useMemo } from 'react';

export type OrbState = 'idle' | 'listening' | 'speaking' | 'tool_call' | 'reconnecting';

interface VoiceOrbProps {
  state: OrbState;
  size?: number;
  audioLevel?: number; // 0-1, from Web Audio analyser
}

export function VoiceOrb({ state, size = 160, audioLevel = 0 }: VoiceOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);
  const angleRef = useRef(0);

  const colors = useMemo(() => ({
    c1: '#22D3EE', // cyan-400
    c2: '#818CF8', // indigo-400
    c3: '#C084FC', // purple-400
    c4: '#38BDF8', // sky-400
    bg: '#0F172A', // slate-900
  }), []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const center = size / 2;
    const baseRadius = size * 0.38;

    function getSpeedMultiplier(): number {
      switch (state) {
        case 'listening': return 1.5 + audioLevel * 2;
        case 'speaking': return 2 + audioLevel * 1.5;
        case 'tool_call': return 0.5;
        case 'reconnecting': return 0.2;
        default: return 0.8;
      }
    }

    function getRadiusMultiplier(): number {
      switch (state) {
        case 'listening': return 1 + audioLevel * 0.15;
        case 'speaking': return 1 + audioLevel * 0.1;
        case 'tool_call': return 0.9;
        case 'reconnecting': return 0.85;
        default: return 1;
      }
    }

    function getOpacity(): number {
      return state === 'reconnecting' ? 0.5 : 1;
    }

    function draw() {
      if (!ctx) return;
      const speed = getSpeedMultiplier();
      const radiusMul = getRadiusMultiplier();
      const opacity = getOpacity();

      angleRef.current += speed * 0.02;
      const angle = angleRef.current;

      ctx.clearRect(0, 0, size, size);
      ctx.globalAlpha = opacity;

      // Background circle
      ctx.beginPath();
      ctx.arc(center, center, baseRadius * radiusMul, 0, Math.PI * 2);
      ctx.fillStyle = colors.bg;
      ctx.fill();

      // Draw multiple gradient layers with blur effect
      ctx.filter = 'blur(8px)';

      const layers = [
        { color: colors.c1, speed: 1, offset: 0 },
        { color: colors.c2, speed: -0.7, offset: Math.PI * 0.5 },
        { color: colors.c3, speed: 1.3, offset: Math.PI },
        { color: colors.c4, speed: -1.1, offset: Math.PI * 1.5 },
      ];

      for (const layer of layers) {
        const layerAngle = angle * layer.speed + layer.offset;
        const r = baseRadius * radiusMul * 0.6;
        const x = center + Math.cos(layerAngle) * r * 0.3;
        const y = center + Math.sin(layerAngle) * r * 0.3;

        const gradient = ctx.createRadialGradient(x, y, 0, x, y, r);
        gradient.addColorStop(0, layer.color + 'CC');
        gradient.addColorStop(0.5, layer.color + '66');
        gradient.addColorStop(1, layer.color + '00');

        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
      }

      ctx.filter = 'none';

      // Inner glow
      const innerGlow = ctx.createRadialGradient(center, center, 0, center, center, baseRadius * radiusMul * 0.5);
      innerGlow.addColorStop(0, 'rgba(255,255,255,0.1)');
      innerGlow.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.beginPath();
      ctx.arc(center, center, baseRadius * radiusMul * 0.5, 0, Math.PI * 2);
      ctx.fillStyle = innerGlow;
      ctx.fill();

      ctx.globalAlpha = 1;
      animationRef.current = requestAnimationFrame(draw);
    }

    draw();

    return () => {
      cancelAnimationFrame(animationRef.current);
    };
  }, [state, audioLevel, size, colors]);

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      {/* Outer glow */}
      <div
        className="absolute inset-0 rounded-full"
        style={{
          background: 'radial-gradient(circle, rgba(56,189,248,0.15) 0%, transparent 70%)',
          animation: 'orb-glow 3.5s ease-in-out infinite',
          transform: `scale(${1.3 + audioLevel * 0.2})`,
        }}
      />
      <canvas
        ref={canvasRef}
        style={{ width: size, height: size, borderRadius: '50%' }}
      />
    </div>
  );
}
