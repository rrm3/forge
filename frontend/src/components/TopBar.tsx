/**
 * TopBar - Subtle persistent top bar for all intake screens.
 *
 * Shows DS logo (left) and user avatar + name with sign-out dropdown (right).
 * Height: 48px, white background with bottom border.
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, RotateCcw, UserRoundCog, Settings, Code } from 'lucide-react';
import { useAuth } from '../auth/useAuth';
import { useAdminStore } from '../state/adminStore';
import { resetIntake } from '../api/client';
import { intakeTitle } from '../program';
import { UserAvatar } from './UserAvatar';
import type { UserProfile } from '../api/types';

const isDevMode = window.location.hostname === 'localhost';

interface TopBarProps {
  profile?: UserProfile | null;
}

export function TopBar({ profile }: TopBarProps = {}) {
  const navigate = useNavigate();
  const { isAdmin, isDepartmentAdmin, adminMode, toggleAdminMode } = useAdminStore();
  const hasAdminAccess = isAdmin || isDepartmentAdmin;
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const [showMasqueradeInput, setShowMasqueradeInput] = useState(false);
  const [masqueradeEmail, setMasqueradeEmail] = useState('');
  const activeMasquerade = localStorage.getItem('forge-masquerade');
  const menuRef = useRef<HTMLDivElement>(null);
  const masqueradeInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  if (!user) return null;

  return (
    <div className="z-30 shrink-0">
      <div
        className="flex items-center justify-between px-4"
        style={{
          height: 48,
          backgroundColor: '#FFFFFF',
          borderBottom: '1px solid #E2E8F0',
        }}
      >
      {/* Left: DS logo + AI Tuesdays */}
      <div className="flex items-center gap-3">
        <img src="/ds-logo.svg" alt="Digital Science" style={{ height: 24 }} />
        <span style={{ color: '#CBD5E1', fontSize: 18, fontWeight: 300 }}>|</span>
        <img src="/ai-tuesdays-logo.png" alt="AI Tuesdays" style={{ height: 22, filter: 'invert(1)' }} />
      </div>

      {/* Right: Avatar + name + dropdown */}
      <div ref={menuRef} className="relative">
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 rounded-full px-1.5 py-1 transition-colors"
          style={{ cursor: 'pointer' }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#F1F5F9'; }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        >
          <UserAvatar
            name={user.name || user.email}
            avatarUrl={profile?.avatar_url}
            title={profile?.title}
            department={profile?.department}
            size={28}
          />
          <span
            style={{
              color: '#4A5568',
              fontSize: 14,
              fontWeight: 500,
              fontFamily: "'Inter', system-ui, sans-serif",
            }}
          >
            {user.name}
          </span>
        </button>

        {open && (
          <div
            className="absolute right-0 top-full mt-1 rounded-lg shadow-lg overflow-hidden z-50 border whitespace-nowrap"
            style={{
              backgroundColor: '#FFFFFF',
              borderColor: '#E2E8F0',
              minWidth: 180,
            }}
          >
            {adminMode && (
              <button
                onClick={async () => {
                  setOpen(false);
                  if (!confirm(`Reset ${intakeTitle()}? This will delete your intake session and all captured profile data.`)) return;
                  try {
                    await resetIntake();
                    // Hard reload to clear all in-memory state (session context, profile, etc.)
                    window.location.href = '/day1';
                  } catch (err) {
                    console.error('Failed to reset intake:', err);
                    alert('Failed to reset intake.');
                  }
                }}
                className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm transition-colors"
                style={{ color: '#D97706' }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#FFFBEB'; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
              >
                <RotateCcw className="w-4 h-4" strokeWidth={1.5} />
                Reset {intakeTitle()}
              </button>
            )}
            {hasAdminAccess && (
              <button
                onClick={() => {
                  setOpen(false);
                  navigate('/admin');
                }}
                className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm transition-colors"
                style={{ color: '#4A5568' }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#F1F5F9'; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
              >
                <Settings className="w-4 h-4" strokeWidth={1.5} />
                Admin
              </button>
            )}
            {isAdmin && (
              <button
                onClick={() => {
                  toggleAdminMode();
                }}
                className="flex items-center justify-between w-full px-4 py-2.5 text-sm transition-colors"
                style={{ color: '#4A5568' }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#F1F5F9'; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
              >
                <span className="flex items-center gap-2.5">
                  <Code className="w-4 h-4" strokeWidth={1.5} />
                  Admin Mode
                </span>
                <span
                  className="relative inline-block rounded-full transition-colors"
                  style={{
                    width: 32,
                    height: 18,
                    backgroundColor: adminMode ? 'var(--color-primary)' : '#CBD5E1',
                  }}
                >
                  <span
                    className="absolute top-0.5 rounded-full bg-white transition-all shadow-sm"
                    style={{
                      width: 14,
                      height: 14,
                      left: adminMode ? 16 : 2,
                    }}
                  />
                </span>
              </button>
            )}
            {isAdmin && isDevMode && !showMasqueradeInput && (
              <button
                onClick={() => {
                  setShowMasqueradeInput(true);
                  setOpen(false);
                  setTimeout(() => masqueradeInputRef.current?.focus(), 50);
                }}
                className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm transition-colors"
                style={{ color: '#4A5568' }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#F1F5F9'; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
              >
                <UserRoundCog className="w-4 h-4" strokeWidth={1.5} />
                Masquerade as...
              </button>
            )}
            <button
              onClick={() => { setOpen(false); signOut(); }}
              className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm transition-colors"
              style={{ color: '#4A5568' }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#F1F5F9'; }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            >
              <LogOut className="w-4 h-4" strokeWidth={1.5} />
              Sign Out
            </button>
          </div>
        )}
      </div>
      </div>

      {/* Masquerade email input (slides in when triggered from dropdown) */}
      {showMasqueradeInput && (
        <div
          className="flex items-center gap-2 px-4"
          style={{
            height: 40,
            backgroundColor: '#FFFBEB',
            borderBottom: '1px solid #FDE68A',
          }}
        >
          <span style={{ fontSize: 13, color: '#92400E', fontWeight: 500, fontFamily: "'Satoshi', system-ui, sans-serif" }}>
            Masquerade as:
          </span>
          <form
            className="flex items-center gap-2 flex-1"
            onSubmit={(e) => {
              e.preventDefault();
              const email = masqueradeEmail.trim();
              if (email && email.includes('@')) {
                localStorage.setItem('forge-masquerade', email);
                window.location.reload();
              }
            }}
          >
            <input
              ref={masqueradeInputRef}
              type="email"
              placeholder="user@digitalscience.com"
              value={masqueradeEmail}
              onChange={(e) => setMasqueradeEmail(e.target.value)}
              className="flex-1 rounded px-2 py-1 text-sm border outline-none"
              style={{
                borderColor: '#FDE68A',
                backgroundColor: '#FFFFFF',
                fontFamily: "'Inter', system-ui, sans-serif",
                fontSize: 13,
              }}
            />
            <button
              type="submit"
              className="rounded px-3 py-1 text-xs font-medium"
              style={{
                backgroundColor: '#D97706',
                color: '#FFFFFF',
                fontFamily: "'Satoshi', system-ui, sans-serif",
              }}
            >
              Go
            </button>
            <button
              type="button"
              onClick={() => { setShowMasqueradeInput(false); setMasqueradeEmail(''); }}
              className="rounded px-2 py-1 text-xs"
              style={{ color: '#92400E', fontFamily: "'Satoshi', system-ui, sans-serif" }}
            >
              Cancel
            </button>
          </form>
        </div>
      )}

      {/* Active masquerade banner */}
      {activeMasquerade && (
        <div
          className="flex items-center justify-center gap-3 px-4"
          style={{
            height: 32,
            backgroundColor: '#FEF3C7',
            borderBottom: '1px solid #FDE68A',
          }}
        >
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: '#92400E',
              fontFamily: "'Satoshi', system-ui, sans-serif",
              letterSpacing: '0.03em',
              textTransform: 'uppercase',
            }}
          >
            Viewing as: {activeMasquerade}
          </span>
          <button
            onClick={() => {
              localStorage.removeItem('forge-masquerade');
              window.location.reload();
            }}
            className="rounded px-2 py-0.5 text-xs font-medium transition-colors"
            style={{
              backgroundColor: '#D97706',
              color: '#FFFFFF',
              fontFamily: "'Satoshi', system-ui, sans-serif",
              cursor: 'pointer',
            }}
          >
            Exit
          </button>
        </div>
      )}

    </div>
  );
}
