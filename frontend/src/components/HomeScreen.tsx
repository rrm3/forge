import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lightbulb, Compass, Star, Sunrise, Trophy, ArrowRight } from 'lucide-react';
import { useSession } from '../state/SessionContext';
import { useAuth } from '../auth/useAuth';
import { getProfile, listUserIdeas } from '../api/client';
import { wrapupTitle } from '../program';
import type { SessionType, UserProfile, UserIdea } from '../api/types';

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
  const { startTypedSession, dispatch, state } = useSession();
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [ideas, setIdeas] = useState<UserIdea[]>([]);
  const [ideasLoaded, setIdeasLoaded] = useState(false);

  useEffect(() => {
    if (user) {
      getProfile().then(setProfile).catch(() => {});
      listUserIdeas().then((result) => {
        result.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
        setIdeas(result);
        setIdeasLoaded(true);
      }).catch(() => setIdeasLoaded(true));
    }
  }, [user]);

  const sessionCount = state.sessions.length;
  const greeting = getGreeting(profile, sessionCount);
  const nonIntakeSessions = state.sessions.filter(s => s.type !== 'intake');
  const isFirstVisit = nonIntakeSessions.length === 0;
  const hasIdeas = ideasLoaded && ideas.length > 0;

  function handleChatIdea(idea: UserIdea) {
    dispatch({
      type: 'SET_IDEA_CONTEXT',
      idea: { idea_id: idea.idea_id, title: idea.title, description: idea.description, tags: idea.tags },
    });
    startTypedSession('chat', idea.idea_id);
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Greeting */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight" style={{ color: 'var(--color-text-primary)' }}>
            {greeting}
          </h1>
          <p className="mt-2 text-base" style={{ color: 'var(--color-text-muted)' }}>
            {hasIdeas && isFirstVisit
              ? 'Here are the ideas we captured from your conversation. Pick one to explore, or try something else.'
              : 'Choose what you\'d like to work on today.'}
          </p>
        </div>

        {/* Two-column layout: main content + ideas sidebar */}
        <div className={hasIdeas ? 'flex flex-col lg:flex-row gap-6' : ''}>
          {/* Main content */}
          <div className={hasIdeas ? 'flex-1 min-w-0' : 'max-w-lg'}>
            {/* Action buttons */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {ACTION_BUTTONS.map((btn) => (
                <button
                  key={btn.type}
                  onClick={() => {
                    if (btn.type === 'wrapup') {
                      // Singleton: reuse existing wrapup for this week instead of creating a duplicate
                      const existing = state.sessions.find(s => s.type === 'wrapup' && s.title === wrapupTitle());
                      if (existing) {
                        navigate(`/chat/${existing.session_id}`);
                        return;
                      }
                    }
                    startTypedSession(btn.type);
                  }}
                  className="group flex items-center gap-3 px-5 py-4 rounded-xl border bg-white hover:bg-[var(--color-primary-subtle)] hover:border-[var(--color-primary)] text-left transition-all duration-200 cursor-pointer"
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
                    {btn.type === 'wrapup' ? wrapupTitle() : btn.label}
                  </span>
                </button>
              ))}

              {/* Browse Tips & Tricks */}
              <button
                onClick={() => navigate('/tips')}
                className="group flex items-center justify-center gap-2 px-5 py-4 rounded-xl border text-center transition-all duration-200 sm:col-span-2 hover:opacity-90 cursor-pointer"
                style={{
                  backgroundColor: '#EEF0FF',
                  borderColor: '#C7D2FE',
                  color: '#4F46E5',
                }}
              >
                <Trophy className="w-4 h-4" strokeWidth={1.5} />
                <span className="text-sm font-medium">Browse Tips & Tricks</span>
              </button>

              {/* Guru link */}
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

          {/* Ideas sidebar - shown on right on desktop, below on mobile */}
          {hasIdeas && (
            <div className="w-full lg:w-80 xl:w-96 flex-shrink-0">
              <div
                className="rounded-xl border p-4"
                style={{ backgroundColor: 'var(--color-surface-white)', borderColor: 'var(--color-border)' }}
              >
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    {isFirstVisit ? 'Your ideas' : 'Ideas to explore'}
                  </h2>
                  {ideas.length > 3 && (
                    <button
                      onClick={() => navigate('/ideas')}
                      className="flex items-center gap-1 text-xs font-medium transition-colors hover:opacity-80"
                      style={{ color: 'var(--color-primary)' }}
                    >
                      View all ({ideas.length})
                      <ArrowRight className="w-3 h-3" strokeWidth={2} />
                    </button>
                  )}
                </div>
                <div className="space-y-1.5">
                  {ideas.slice(0, 5).map((idea) => (
                    <button
                      key={idea.idea_id}
                      onClick={() => handleChatIdea(idea)}
                      className="group w-full flex items-start gap-2.5 px-3 py-2.5 rounded-lg text-left transition-all duration-150 hover:bg-[var(--color-primary-subtle)] cursor-pointer"
                    >
                      <Star
                        className="flex-shrink-0 w-4 h-4 mt-0.5"
                        style={{ color: 'var(--color-text-placeholder)' }}
                        strokeWidth={1.5}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate group-hover:text-[var(--color-primary)] transition-colors" style={{ color: 'var(--color-text-primary)' }}>
                          {idea.title}
                        </p>
                        {idea.description && (
                          <p
                            className="text-xs mt-0.5"
                            style={{
                              color: 'var(--color-text-muted)',
                              display: '-webkit-box',
                              WebkitLineClamp: 1,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                            }}
                          >
                            {idea.description}
                          </p>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
                {ideas.length > 5 && (
                  <button
                    onClick={() => navigate('/ideas')}
                    className="w-full mt-2 py-2 text-xs font-medium text-center rounded-lg transition-colors hover:bg-[var(--color-surface-raised)]"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    +{ideas.length - 5} more ideas
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
