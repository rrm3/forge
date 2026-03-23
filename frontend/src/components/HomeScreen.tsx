import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lightbulb, Compass, Star, Sunrise, Trophy } from 'lucide-react';
import { useSession } from '../state/SessionContext';
import { useAuth } from '../auth/useAuth';
import { getProfile } from '../api/client';
import type { SessionType, UserProfile } from '../api/types';

const ACTION_BUTTONS: { type: SessionType; label: string; Icon: typeof Lightbulb }[] = [
  { type: 'tip', label: 'Share a Tip or Trick', Icon: Lightbulb },
  { type: 'stuck', label: "I'm Stuck", Icon: Compass },
  { type: 'brainstorm', label: 'Brainstorm an Opportunity', Icon: Star },
  { type: 'wrapup', label: 'End-of-Day Wrap-up', Icon: Sunrise },
];

function getGreeting(profile: UserProfile | null, sessionCount: number): string {
  const name = profile?.name?.split(' ')[0] || '';
  const now = new Date();
  const dayOfWeek = now.getDay();
  const isTuesday = dayOfWeek === 2;

  if (isTuesday) {
    return name ? `Ready for AI Tuesday, ${name}?` : 'Ready for AI Tuesday?';
  }

  if (sessionCount >= 5) {
    return name
      ? `You're building momentum, ${name}.`
      : "You're building momentum.";
  }

  if (sessionCount > 0) {
    return name ? `Welcome back, ${name}.` : 'Welcome back.';
  }

  return name ? `Welcome, ${name}.` : 'Welcome to AI Tuesdays.';
}

export function HomeScreen() {
  const navigate = useNavigate();
  const { startTypedSession, state } = useSession();
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);

  useEffect(() => {
    if (user) {
      getProfile().then(setProfile).catch(() => {});
    }
  }, [user]);

  const sessionCount = state.sessions.length;
  const greeting = getGreeting(profile, sessionCount);

  return (
    <div className="flex flex-col items-center justify-center h-full px-6 text-center">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight" style={{ color: 'var(--color-text-primary)' }}>
          {greeting}
        </h1>
        <p className="mt-3 text-base" style={{ color: 'var(--color-text-muted)' }}>
          Choose what you'd like to work on today.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
        {ACTION_BUTTONS.map((btn) => (
          <button
            key={btn.type}
            onClick={() => startTypedSession(btn.type)}
            className="group flex items-center gap-3 px-5 py-4 rounded-xl border bg-white hover:bg-[var(--color-primary-subtle)] hover:border-[var(--color-primary)] text-left transition-all duration-200"
            style={{ borderColor: 'var(--color-border)' }}
          >
            <div
              className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-colors duration-200"
              style={{ backgroundColor: 'var(--color-surface-raised)' }}
            >
              <btn.Icon
                className="w-5 h-5 transition-colors duration-200 group-hover:text-[var(--color-primary)]"
                style={{ color: 'var(--color-text-muted)' }}
                strokeWidth={1.5}
              />
            </div>
            <span
              className="text-sm font-medium transition-colors duration-200 group-hover:text-[var(--color-primary)]"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              {btn.label}
            </span>
          </button>
        ))}

        {/* Browse Tips & Tricks */}
        <button
          onClick={() => navigate('/tips')}
          className="group flex items-center justify-center gap-2 px-5 py-4 rounded-xl border text-center transition-all duration-200 sm:col-span-2 hover:opacity-90"
          style={{
            backgroundColor: '#EEF0FF',
            borderColor: '#C7D2FE',
            color: '#4F46E5',
          }}
        >
          <Trophy className="w-4 h-4" strokeWidth={1.5} />
          <span className="text-sm font-medium">Browse Tips & Tricks</span>
        </button>

        {/* Guru link - full width across both columns */}
        <a
          href="https://app.getguru.com/page/31fe984d-f863-4487-8080-849d9f3461ef"
          target="_blank"
          rel="noopener noreferrer"
          className="group relative flex items-center justify-between px-5 rounded-xl transition-all duration-200 sm:col-span-2 overflow-hidden"
          style={{
            backgroundImage: 'url(/ai-tuesdays-bg.jpg)',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            height: '52px',
          }}
        >
          <img
            src="/ai-tuesdays-logo.png"
            alt="AI Tuesdays"
            className="h-6"
            style={{ filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.3))', marginTop: '-2px' }}
          />
          <span className="text-sm text-white font-bold">View on Guru &#x2197;</span>
        </a>
      </div>
    </div>
  );
}
