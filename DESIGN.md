# Design System — Forge (AI Tuesdays)

## Product Context
- **What this is:** An internal AI coaching companion for Digital Science's "Forge" initiative, where staff dedicate Tuesdays to AI upskilling
- **Who it's for:** 700 employees across Digital Science (all departments, all skill levels)
- **Space/industry:** Corporate L&D, AI coaching, internal tools
- **Project type:** Web app (React + Vite + Tailwind)

## Aesthetic Direction
- **Direction:** Minimal-Warm
- **Decoration level:** Minimal — typography, color, and whitespace do all the work. The voice orb is the one decorative exception.
- **Mood:** A capable colleague who's easy to talk to. Professional and AI-native without being cold or clinical. Between ChatGPT's austerity and Claude's literary warmth.
- **Reference products:** ChatGPT, Claude, SmoothUI component library (MIT, https://smoothui.dev — good reference for future component design)

## Typography
- **Display/Hero:** Satoshi 700 — contemporary geometric sans by Fontshare. More personality than Inter, reads as "modern tech product" without being generic. Free.
- **Body:** Satoshi 400/500 — same family for cohesion, excellent readability at paragraph length
- **UI/Labels:** Satoshi 500
- **Data/Tables:** Geist Mono (tabular-nums support, clean) — by Vercel
- **Code:** Geist Mono
- **Loading:** Fontshare CDN `https://api.fontshare.com/v2/css?f[]=satoshi@400,500,600,700&display=swap` and Google Fonts for Geist Mono
- **Scale:** 1.25 ratio

| Name | Size | Weight | Usage |
|------|------|--------|-------|
| xs | 12px / 0.75rem | 500 | Captions, timestamps, meta |
| sm | 14px / 0.875rem | 400-500 | UI text, buttons, labels |
| base | 16px / 1rem | 400 | Body text, messages |
| lg | 18px / 1.125rem | 500 | Subheadings |
| xl | 20px / 1.25rem | 600 | Section headings |
| 2xl | 24px / 1.5rem | 600 | Page headings |
| 3xl | 30px / 1.875rem | 700 | Hero subheading |
| 4xl | 36px / 2.25rem | 700 | Hero heading |

## Color
- **Approach:** Restrained — one accent color + slate neutrals
- **Primary:** `#159AC9` — brand teal-blue, used for actions, active states, links
- **Primary hover:** `#1287B3`
- **Primary subtle:** `#E8F4F8` — light tint for backgrounds, hover states
- **Text primary:** `#1A1F25`
- **Text secondary:** `#4A5568`
- **Text muted:** `#64748B`
- **Text placeholder:** `#94A3B8`
- **Surface:** `#FAFBFC` — base background (not pure white)
- **Surface raised:** `#F1F5F9` — cards, sidebar, elevated surfaces
- **Surface white:** `#FFFFFF` — chat area, modals
- **Border:** `#E2E8F0` — slate-200
- **User bubble:** `#EDF2F7` — slate-100
- **Semantic:** success `#059669`, warning `#D97706`, error `#DC2626`, info `#159AC9`

**Neutrals rationale:** Slate grays (slight blue undertone) rather than pure cool grays. The blue undertone harmonizes with the teal-blue primary accent and makes surfaces feel intentionally designed rather than default.

**Dark mode strategy:** Darken surfaces, reduce saturation 10-20%, lighten primary slightly for contrast. Reference the dark mode tokens in the preview page at `/tmp/design-consultation-preview-forge.html`.

## Spacing
- **Base unit:** 4px
- **Density:** Comfortable
- **Scale:**

| Token | Value | Usage |
|-------|-------|-------|
| 2xs | 2px | Hairline gaps |
| xs | 4px | Tight padding, icon gaps |
| sm | 8px | Compact padding, small gaps |
| md | 16px | Standard padding, component spacing |
| lg | 24px | Section padding |
| xl | 32px | Large section gaps |
| 2xl | 48px | Page-level spacing |
| 3xl | 64px | Major section breaks |

## Layout
- **Approach:** Grid-disciplined — sidebar + centered content for a chat product
- **Sidebar width:** 260-288px
- **Max content width:** 768px (chat messages)
- **Grid:** Single column for chat, 2-column for action buttons
- **Breakpoints:** Mobile < 768px (sidebar hidden behind hamburger), tablet 768-1024px (collapsible sidebar), desktop > 1024px (sidebar always visible)
- **Border radius:**

| Token | Value | Usage |
|-------|-------|-------|
| sm | 6px | Small elements, chips, badges |
| md | 10px | Buttons, inputs, cards |
| lg | 14px | Modals, large cards, chat input |
| full | 9999px | Avatars, pills, mic button |

## Motion
- **Approach:** Minimal-functional everywhere, expressive only for the mic button
- **Easing:** enter: ease-out, exit: ease-in, move: ease-in-out
- **Duration:**

| Token | Value | Usage |
|-------|-------|-------|
| micro | 100ms | Hover states, focus rings |
| short | 200ms | State transitions, expanding/collapsing |
| medium | 300ms | Panel transitions, sidebar |
| long | 400-700ms | Mic button gradient rotation only |

- **Mic button animation:** 4s gradient rotation (see Voice Input Mic Button section)
- **Streaming indicator:** Bouncing dots, 1.4s ease-in-out infinite with 0.2s stagger

## Voice Input Mic Button

The mic button is the singular expressive element in an otherwise restrained UI. It inherits the Voice Orb's aesthetic role (full orb preserved on `voice-mode-wip` branch for potential future use).

**Gradient palette** (from Voice Orb):
- `#22D3EE` (cyan-400)
- `#818CF8` (indigo-400)
- `#C084FC` (purple-400)
- `#38BDF8` (sky-400)

**Idle state:**
- 40px circle on desktop, 56px on mobile (< 768px)
- Multi-color gradient background with slow 4s rotation
- 2px pulse ring in primary-subtle (#E8F4F8), 2s ease-in-out infinite
- Lucide Mic icon, 20px, white, 1.5px stroke
- Positioned bottom-right of input area, left of send button. Visually dominant over the 32px flat send button.

**Recording state:**
- Gradient intensifies with audio level
- Scrolling waveform fills the textarea area (bars in primary color, dots in text-placeholder for silence)
- Cancel (X) left, duration timer center-right (Geist Mono, xs, tabular-nums), Stop (Check) right
- 200ms ease-out transition in

**Keyboard shortcut:** CapsLock with smart detection. Quick press (< 500ms) = toggle. Hold > 500ms = push-to-talk.

**Reduced motion:** Disable gradient rotation and pulse ring if `prefers-reduced-motion`.

## Icons
- **Style:** Outline stroke icons, 1.5px stroke weight
- **Library:** Phosphor Icons or Lucide (both MIT). Clean, minimal outlines.
- **Session type icons:**
  - Tip: lightbulb
  - Stuck: compass
  - Brainstorm: star
  - Wrap-up: sunrise
  - Chat: message bubble
  - Intake: (not shown in session list while incomplete)

## Component Library Reference
- **SmoothUI** (https://smoothui.dev, MIT license) — the design aesthetic of SmoothUI components aligns well with Forge's minimal-warm direction. When building future components (toggles, sliders, cards, etc.), reference SmoothUI's implementation patterns and visual language. Uses React + Tailwind + Motion (Framer Motion).

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-20 | Initial design system created | /design-consultation based on "between ChatGPT and Claude" direction |
| 2026-03-20 | Satoshi over Inter | More geometric character, reads as "AI-native" vs generic. Biggest lever for product personality. |
| 2026-03-20 | Slate neutrals over cool grays | Blue undertone harmonizes with teal-blue primary, makes surfaces feel designed |
| 2026-03-20 | Conic-gradient voice orb (SmoothUI-style) | Multi-color flowing animation, pure CSS, MIT reference. The one expressive element in a restrained UI. |
| 2026-03-20 | Phosphor/Lucide icons over emoji | Clean outline strokes match minimal aesthetic. Emoji looked inconsistent across platforms. |
| 2026-03-20 | SmoothUI as component reference | MIT library whose aesthetic aligns with Forge's minimal-warm direction. Reference for future components. |
| 2026-03-21 | Voice Orb replaced by gradient mic button | Full orb retired with OpenAI Realtime mode (on voice-mode-wip branch). Mic button inherits the orb's gradient as Forge's signature expressive element. |
| 2026-03-21 | Voice-first unified input | Textarea always visible, large gradient mic button encourages voice. CapsLock shortcut (smart detection: toggle or hold-to-talk). Transcript inserts at cursor position. |
