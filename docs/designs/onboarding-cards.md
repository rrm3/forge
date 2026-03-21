# Onboarding Cards - Design Spec

## Overview
First-run experience for AI Tuesdays. Four full-bleed story cards shown before the
intake chat conversation. Sets context, builds trust, transitions naturally into chat.

## Card Sequence

### Card 1: Think, play, learn by doing

**Body:** AI Tuesdays gives you one day a week to explore what AI means for your work.
Not a course. Not a checkbox. Time the company is making for you to experiment, get
curious, and discover new ways to solve the problems you care about.

**Visual:** Scattered soft gradient circles of varying sizes, overlapping gently.
The mic button gradient palette expanded into a decorative field.

### Card 2: Your AI companion

**Body:** This is your home base for the next 12 weeks. It learns what you're working
on, suggests ideas that fit, and helps when you're stuck. Think of it as a
knowledgeable colleague who's always available.

**Visual:** A larger central circle (companion) with smaller orbiting dots around it.
Suggests connection and personalization.

### Card 3: Better together

**Body:** As you discover what works, we'll capture tips and practices you can share
with everyone. Later in the program, we want to connect people across functions to
work on projects that drive real value.

**Visual:** Multiple circles connected by thin lines. Network/constellation feel.
Suggests people connecting.

### Card 4: A quick conversation to start

**Body:** Before jumping in, it helps to know a bit about you - your role, what you're
working on, what you're curious about. Takes about 10 minutes. Speak or type,
whatever feels natural.

Pro tip: press CapsLock to record.

**Visual:** A single circle with a subtle pulse ring (echoing the mic button).
Visual bridge to the chat.

**CTA:** "Let's go" button (primary bg, centered)

## Visual Design

### Illustration style
Abstract geometric shapes using the Voice Orb gradient palette:
* `#22D3EE` (cyan-400)
* `#818CF8` (indigo-400)
* `#C084FC` (purple-400)
* `#38BDF8` (sky-400)

Pure CSS/SVG - no external image assets. Shapes are soft circles, arcs, blobs with
gradient fills at varying opacities. Each card has a unique arrangement but they share
the same palette for continuity.

The gradient palette connects the onboarding visuals to the mic button in the chat,
creating a visual thread through the entire experience.

### Layout (desktop)
```
┌──────────────────────────────────────────┐
│                                          │
│      [ geometric shapes area ]           │
│      ( ~40% of card height )             │
│                                          │
│   Headline                               │
│   Satoshi 700, 24px (2xl)                │
│                                          │
│   Body text goes here, 2-3 sentences.    │
│   Satoshi 400, 16px (base)              │
│   Max-width ~480px, centered.            │
│                                          │
│                                          │
│       ●  ○  ○  ○     [Next →]           │
│                                          │
└──────────────────────────────────────────┘
```

* Cards centered at max-w-lg (512px)
* Full viewport height (min-h-screen)
* Content vertically centered
* Surface background (#FAFBFC)

### Layout (mobile)
* Full width, no horizontal margins on shapes
* Shapes scale down proportionally
* Swipe left/right for navigation (in addition to buttons)
* "Next" / "Let's go" buttons: 48px min touch target

### Typography
* Headlines: Satoshi 700, 2xl (24px/1.5rem)
* Body: Satoshi 400, base (16px/1rem), text-secondary color (#4A5568)
* "Pro tip" on Card 4: Satoshi 500, sm (14px), text-muted color (#64748B)

### Navigation
* Dot indicators: 8px circles, primary (#159AC9) for active, border (#E2E8F0) for inactive
* "Next" button: right-aligned, primary text color, sm font, no fill (text button)
* Card 4: "Let's go" replaces "Next" - primary bg, white text, rounded-md, centered
* Keyboard: arrow keys navigate, Enter on Card 4 starts chat
* Transition between cards: 300ms ease-out (DESIGN.md `medium` token)

## Transition to Chat

When "Let's go" is pressed:
1. Cards cross-fade out (300ms)
2. Chat area fades in with a subtle gradient wash at the top (gradient palette at 3-5% opacity, fading to white)
3. Intake session starts (startTypedSession('intake'))
4. AI greeting streams in

The gradient wash at the top of the chat area connects visually to the onboarding cards
and adds warmth to what would otherwise be a blank white chat area.

### AI greeting treatment
The first AI message during intake should have slightly different visual treatment:
* Larger text (lg instead of base) for the opening line
* Or: rendered inside a subtle card container with surface-raised bg
* Purpose: distinguish the greeting from regular messages, make it feel like a continuation of the cards

## State handling

| State | Behavior |
|-------|----------|
| First visit (no intake started) | Show 4 cards, then chat |
| Returning (intake in progress) | Skip cards, go straight to chat |
| Returning (intake complete) | Never show IntakeView |
| Back button during cards | Go to previous card (or do nothing on Card 1) |

## Content source
Card copy validated by content team via AI Tuesdays briefing materials.
See: `/Users/rmcgrath/Documents/caio/ds-twin/projects/forge/forge-onboarding-cards-content.md`

Key tone guidance from content team:
* "Think, play, learn by doing" is the validated tagline (Alison Mitchell)
* Avoid: "initiative," "leverage," "upskill," "assessment," "transformation"
* Data capture framed as employee benefit: "the more it learns about you, the more useful it becomes"
* "A conversation, not a form" for the intake
