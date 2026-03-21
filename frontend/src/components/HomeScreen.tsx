import { useSession } from '../state/SessionContext';
import type { SessionType } from '../api/types';

const ACTION_BUTTONS: { type: SessionType; label: string; icon: string }[] = [
  { type: 'tip', label: 'Share a Tip or Trick', icon: '💡' },
  { type: 'stuck', label: "I'm Stuck", icon: '🧭' },
  { type: 'brainstorm', label: 'Brainstorm an Opportunity', icon: '⭐' },
  { type: 'wrapup', label: 'End-of-Day Wrap-up', icon: '🌅' },
];

export function HomeScreen() {
  const { startTypedSession, sendChatMessage } = useSession();

  return (
    <div className="flex flex-col items-center justify-center h-full px-6 text-center bg-white">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-[#21262E]">Welcome to AI Tuesdays</h2>
        <p className="mt-2 text-sm text-[#5e7a88] max-w-md">
          Your AI companion for the Forge program. Choose an action below or start a free-form chat.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 w-full max-w-md mb-6">
        {ACTION_BUTTONS.map((btn) => (
          <button
            key={btn.type}
            onClick={() => startTypedSession(btn.type)}
            className="px-4 py-3 rounded-xl border border-[#d9dfe1] bg-white hover:border-[#159AC9] hover:bg-[#f3f6f7] text-sm text-[#3A4853] hover:text-[#159AC9] transition-colors text-left flex items-center gap-2"
          >
            <span className="text-lg">{btn.icon}</span>
            <span>{btn.label}</span>
          </button>
        ))}
      </div>

      <button
        onClick={() => sendChatMessage('')}
        className="text-sm text-[#5e7a88] hover:text-[#159AC9] transition-colors"
      >
        Or start a free-form chat
      </button>
    </div>
  );
}
