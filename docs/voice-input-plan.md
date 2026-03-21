# Voice Input Plan (v1)

## Decision
Voice-over-GPT-4o (OpenAI Realtime) doesn't meet quality bar for v1. Pivoting to:
* **Text output only** via Claude Opus 4.6 (Bedrock) - already working
* **Voice-first input** via browser mic recording + Gemini 2.5 Flash transcription

## Completed work
* Removed VoiceOrb, VoiceMode, voice splash screen, voice_session WebSocket handler, backend/voice.py, @openai/agents dep
* Voice mode preserved on `voice-mode-wip` branch at commit 9d88f88
* Added Gemini transcription backend endpoint (POST /api/transcribe)
* Added useVoiceRecorder hook and VoiceButton component (acumentum pattern)
* IntakeView goes straight to text (no splash)

## Design: Voice-First Input Component

### Architecture: Unified input
The textarea is always visible. The mic button is large and prominent - visually dominant
over the send button. No separate "voice mode" vs "text mode" toggle. Voice and text
coexist in a single input area. This solves the "append more voice" problem naturally -
the mic is always one tap away.

After sending, the input always returns to voice-first state (mic prominent, textarea
empty). Even if the user typed their last message.

### Mic button (idle state)
* **Size:** 40px circle on desktop, 56px on mobile (< 768px)
* **Style:** Voice Orb gradient background (cyan-400 -> indigo-400 -> purple-400 -> sky-400 from DESIGN.md)
* **Animation:** Slow gradient rotation (4s), replaces the full Voice Orb as Forge's "singular expressive element"
* **Pulse ring:** 2px ring in primary-subtle (#E8F4F8), 2s ease-in-out infinite
* **Icon:** Lucide Mic, 20px, white, 1.5px stroke
* **Position:** Bottom-right of input area, left of send button. Mic is visually dominant (larger + gradient vs send's 32px flat style)
* **Reduced motion:** Disable gradient rotation and pulse if `prefers-reduced-motion`

### Hint text
* First 2-3 interactions per session: "Tap mic or press CapsLock to respond" in text-placeholder color, xs size, below the input
* After that: "Enter to send, Shift+Enter for new line" (standard text hint)
* Placeholder text in textarea: "Type or tap mic to respond..."

### CapsLock keyboard shortcut
* **Smart detection:** Quick press+release (< 500ms) = toggle recording on/off. Hold longer than 500ms = push-to-talk (release stops recording)
* **Recording indicator:** CapsLock keyboard light turns on while recording (hardware feature, free)
* **macOS note:** System CapsLock delay (~200ms) may cause slight lag. Tooltip mentions "System Preferences > Keyboard to disable CapsLock delay" if macOS detected
* **Scope:** Only active when the Forge app/tab is focused
* **CapsLock state:** Toggles ON when pressed, OFF when released = net zero effect on system state

### Recording state
* **Visualization:** Scrolling waveform (acumentum/ChatGPT/Claude pattern)
  * Canvas-based, new bars appear at right edge, scroll left
  * Bars use primary color (#159AC9) for speech, dots in text-placeholder for silence
  * Adaptive normalization with exponential decay (already implemented)
* **Layout:** Waveform expands to fill textarea area. Cancel (X) button left, duration timer center-right (Geist Mono, xs, tabular-nums), Stop (Check) button right
* **Mic button during recording:** Stays visible, gradient intensifies with audio level
* **Transition in:** 200ms ease-out (DESIGN.md `short` token)
* **During AI streaming:** Mic stays active. User can start recording while AI text is still flowing. Sent message queues behind current response.

### Transcription flow
1. User stops recording (tap stop, press CapsLock again, or release CapsLock in hold mode)
2. Waveform freezes at 50% opacity, "Transcribing..." + spinner
3. Audio sent to POST /api/transcribe (Gemini 2.5 Flash)
4. Transcript **inserts at cursor position** in textarea (not appended to end)
   * Uses Selection/Range API for contentEditable or selectionStart/selectionEnd for textarea
   * If no cursor position, appends to end
5. User reviews, edits if needed, hits Send (or Enter)
6. After send: textarea clears, mic returns to prominent idle state

### Error states
* **Mic denied:** Inline error text (red, not a modal). "Microphone access needed. Enable in browser settings." with "Try again" link. Textarea stays available for typing.
* **Transcription failed:** Brief inline error below input, fades after 4s. Returns to idle. Audio is lost (no retry with same audio).
* **No mic found:** "No microphone detected. You can type your response instead."

### Accessibility
* Mic button: `aria-label="Record voice message (CapsLock)"`, `role="button"`
* Mic (recording): `aria-label="Stop recording"`, `aria-pressed="true"`
* Waveform: `aria-hidden="true"` (decorative)
* Duration: announced via `aria-live="polite"` region
* Transcribing state: `aria-live="polite"` announces "Transcribing..."
* Focus ring: 2px primary color, offset 2px
* Touch targets: 40px desktop (48px with padding), 56px mobile

### Responsive behavior
* **Desktop (> 1024px):** 40px mic, CapsLock hint, standard textarea
* **Tablet (768-1024px):** 40px mic, no CapsLock hint (may not have physical keyboard)
* **Mobile (< 768px):** 56px mic, "Tap mic to respond" hint, textarea auto-grows

## DESIGN.md updates needed
* Replace Voice Orb section: the mic button now carries the orb's gradient aesthetic as Forge's signature element. The full orb is retired (saved on voice-mode-wip branch).
* Update Motion section: remove "Voice orb animation" references, add mic button gradient rotation (4s)

## Key files
* `frontend/src/components/VoiceButton.tsx` - mic button + recording UI (needs redesign)
* `frontend/src/components/ChatView.tsx` - chat input integration
* `frontend/src/components/IntakeView.tsx` - intake input integration
* `frontend/src/hooks/useVoiceRecorder.ts` - MediaRecorder hook (mostly done)
* `backend/api/transcription.py` - Gemini transcription endpoint (done)
* `~/dev/acumentum` - reference implementation for waveform, cursor-position insertion

## Branch state
* `main` - current work (voice mode removed, basic VoiceButton in place)
* `voice-mode-wip` - saved at commit 9d88f88 (full OpenAI Realtime voice mode)

## Future considerations (not v1)
* **Real-time transcription:** Gemini Live API supports streaming audio with live transcription. Could show transcript appearing in real-time while user speaks. Significant integration effort.
* **Auto-send:** After transcription, auto-send with a brief preview window + cancel. Once users trust transcription quality.
* **Mode memory:** Remember if a user consistently prefers text, stop nudging voice.
