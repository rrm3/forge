# Intake Chat Screen - Design Spec

## Overview
The chat screen shown immediately after the onboarding cards. Currently feels empty
and unstructured. This spec addresses the structural, visual, and interaction problems.

## Top Bar (global - appears on cards AND chat)

A subtle persistent bar giving the page product-level structure.

* **Height:** 48px
* **Background:** surface-white (#FFFFFF), border-bottom 1px in border color (#E2E8F0)
* **Left:** Digital Science logo (~24px height), left-aligned with 16px left padding
  * TODO: need logo SVG file from Rob
  * Placeholder: "Digital Science" in Satoshi 600, text-secondary
* **Right:** User avatar (28px circle, primary bg, white initials) + name (sm, text-secondary)
  * Click opens dropdown with "Sign Out" (reuse UserMenu pattern)
  * Mobile: avatar only, no name text
* **Center:** "AI Tuesdays" in Satoshi 500, text-muted (optional, may be too busy)

## Centered Conversation Layout

Messages and input in a single flex column that centers vertically when content is short.

**Short conversation (1-3 messages):**
```
┌─ top bar ────────────────────────────────────────┐
│                                                  │
│         (breathing room - flex centers)          │
│                                                  │
│   AI: Hi Robert! Let me get to know you...      │
│                                                  │
│   ┌──────────────────────────────────────┐      │
│   │ Type or tap mic...                🎤 │      │
│   └──────────────────────────────────────┘      │
│   Enter to send, Shift+Enter for new line       │
│                                                  │
│         (breathing room - flex centers)          │
│                                                  │
└──────────────────────────────────────────────────┘
```

**Long conversation (many messages):**
Messages scroll naturally, input pins to bottom. Standard chat layout.

**CSS approach:**
* Outer container: `min-h-[calc(100vh-48px)]` (minus top bar), `flex flex-col justify-center`
* Inner chat area: `flex flex-col max-w-2xl mx-auto w-full`
* When content overflows, `justify-center` has no effect and content fills naturally
* Input area: part of the same flex flow, not position-fixed

## Gradient Wash

Subtle gradient at top of the chat area for warmth:
* Linear gradient from top: gradient palette colors at 2-3% opacity -> transparent
* Fades over first ~200px of the chat area
* Connects visually to the onboarding card aesthetics

## Pre-loaded First Message

The intake session starts silently when the user reaches onboarding Card 2.
By the time they press "Let's go" on Card 4, the AI greeting is ready.

* IntakeView starts the session via `startTypedSession('intake')` when Card 2 is reached
* Messages accumulate in SessionContext state while cards are visible
* When cards dismiss, messages render immediately (no loading dots)
* If message not ready yet: show a subtle shimmer placeholder, not bouncing dots

## First Message Visual Treatment

The AI's first message during intake gets slightly enhanced rendering:
* Opening line rendered at lg size (18px) instead of base (16px)
* Rendered in a subtle card container: surface-raised bg, rounded-lg, padding 16px
* After the first message, all subsequent messages render normally

## CapsLock Floating Hint

Instead of in the onboarding cards, the CapsLock tip appears as a floating
dismissible pill above the chat input after the first AI message renders.

* Position: centered above the input area, 8px gap
* Style: primary-subtle bg (#E8F4F8), rounded-full, CapsLock key icon + text
* Dismisses: on first recording, on X click, or after 15 seconds
* Not shown on mobile/tablet (no CapsLock key)

## AI Greeting System Prompt Update (TODO)

The intake system prompt needs to know the user has already read the onboarding cards.
It should NOT re-introduce AI Tuesdays. Instead it should:
* Jump straight into "I'll be helping you get started today"
* Use structured markdown (bold for key points, not emojis)
* Know what the cards already covered (the why, the companion, the community, the process)

This is a prompt engineering task, not a frontend task. Track as a TODO.

## "Getting to know you" Header

Remove the "AI Tuesdays / Getting to know you" header from the chat screen.
The top bar provides the product branding. The AI's greeting message provides
the context. The header was redundant and added to the "bare" feeling.

## Markdown Rendering

Ensure MessageBubble renders markdown well for all AI messages:
* Bold text for structure
* Lists (numbered and bulleted)
* Proper paragraph spacing
* No emojis in AI responses (prompt guidance, not frontend)
