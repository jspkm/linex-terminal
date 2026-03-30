# Design System - Linex Terminal

## Product Context
- **What this is:** Loyalty program diligence and optimization platform
- **Who it's for:** Linex team (internal ops, deal analysis, investor demos)
- **Space/industry:** Financial data tools, quant terminals, PE/roll-up operations
- **Project type:** Dark-themed data-dense web app with agent chat

## Aesthetic Direction
- **Direction:** Industrial/Utilitarian with a quant edge
- **Decoration level:** Minimal. Typography and data do the work. No gradients, no decorative elements, no card shadows.
- **Mood:** An instrument you get fluent in, not a dashboard you browse. Bloomberg terminal meets modern quant tooling. Precision, density, confidence.
- **Reference sites:** Bloomberg Terminal, Palantir Foundry, Amsflow

## Typography
- **Display/Hero:** Geist (700) - clean, geometric, modern. Crisper than system fonts at small sizes.
- **Body:** Geist (400/500) - same family, seamless pairing with display
- **UI/Labels:** Geist Mono (600) at 10px with letter-spacing 0.06-0.12em for section headers and labels
- **Data/Tables:** Geist Mono (400) - tabular-nums built in, pairs perfectly with Geist body
- **Code:** JetBrains Mono (400) - industry standard for code blocks
- **Loading:** Google Fonts CDN (`https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&family=JetBrains+Mono:wght@400;500`)
- **Scale:**
  - Hero: 48px / 700 / -0.02em tracking
  - H2: 16px / 600
  - Body: 14px / 400 / 1.5 line-height
  - Small: 12px / 400
  - Label: 10px / 600 / 0.06-0.12em tracking (Geist Mono, uppercase)
  - Data: 12-13px / 400 (Geist Mono)
  - Code: 13px / 400 (JetBrains Mono)

## Color
- **Approach:** Restrained. One primary accent + one secondary. Color is rare and meaningful.
- **Background:** `#050607` - near-black
- **Panel:** `#0c0f0f` - card/panel background
- **Panel Alt:** `#101514` - alternate panel
- **Surface:** `#141a18` - tertiary background (green-tinted)
- **Surface Light:** `#1a211e` - lighter surface
- **Border:** `#2e3432` - default border
- **Border Light:** `#3d4542` - lighter border
- **Text Primary:** `#edf3ef` - main text (green-tinted white)
- **Text Secondary:** `#b4c0b8` - supporting text
- **Muted:** `#7a8680` - disabled/placeholder text
- **Accent (Primary):** `#66ff99` - bright green. "Money/growth." Used sparingly for key metrics, active states, CTA.
- **Accent Dim:** `#3bb266` - dimmed green for secondary interactive elements
- **Accent Background:** `rgba(102,255,153,0.06)` - subtle green wash
- **Secondary:** `#00aaff` - blue. Used for interactive elements, links, secondary actions.
- **Semantic:**
  - Success: `#66ff99` (same as accent)
  - Warning: `#ffb347` / bg `rgba(255,179,71,0.06)`
  - Error/Danger: `#ff5d73` / bg `rgba(255,93,115,0.06)`
  - Info: `#5b9bff` / bg `rgba(91,155,255,0.06)`
- **Dark mode:** This IS the dark mode. No light mode planned.
- **Design decision:** Green-tinted neutrals instead of pure grays. Every other terminal uses cool blue-grays. The green tint makes the interface feel alive, reinforces the loyalty/growth brand, and is instantly recognizable.

## Spacing
- **Base unit:** 4px
- **Density:** Compact (professionals want information density)
- **Scale:** 2xs(2) xs(4) sm(8) md(12) lg(16) xl(24) 2xl(32) 3xl(48)
- **Table row padding:** 8px vertical, 12px horizontal
- **Section gaps:** 24-48px
- **Card padding:** 16px internal

## Layout
- **Approach:** Grid-disciplined. Strict columns, predictable alignment.
- **Primary pattern:** Split-pane (main content + agent chat). 60-80% main, 20-40% chat.
- **Grid:** Single column main content with max-width 6xl (1152px)
- **Max content width:** 1200px
- **Border radius:**
  - sm: 2px (badges, tags)
  - md: 4px (buttons, inputs)
  - lg: 6px (cards, panels, chat bubbles)
  - xl: 8px (modals, large containers)
  - full: 9999px (profile badges, circular elements)
- **Data tables are first-class citizens.** Full-width, compact, with sticky headers. Not wrapped in cards with padding.

## Motion
- **Approach:** Minimal-functional. Only transitions that aid comprehension.
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** micro(50ms) short(100-150ms) medium(200ms)
- **What gets motion:** hover states, tab switches, dropdown open/close, loading spinners
- **What does NOT get motion:** page loads, data table rendering, chat messages appearing, scroll

## Anti-Patterns (never use)
- Purple/violet gradients
- 3-column feature grids with icons in colored circles
- Centered everything with uniform spacing
- Card shadows or decorative drop shadows
- Gradient buttons
- Bouncy/spring animations
- Generic stock-photo hero sections
- Rounded bubbly UI (this is a terminal, not a consumer app)
- Light mode (the product is dark by design)

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-29 | Initial design system created | Based on competitive research of Bloomberg, Palantir, Amsflow. Formalized existing dark theme with green-tinted neutrals. |
| 2026-03-29 | Geist over IBM Plex Mono for page font | Crisper at small sizes, better tabular number support via Geist Mono, bridges sans-serif readability with technical feel |
| 2026-03-29 | Green-tinted neutrals kept | Distinctive vs pure-gray competitors. Reinforces money/growth brand. Instantly recognizable. |
| 2026-03-29 | #00aaff added as secondary accent | Already used inline for interactive elements. Formalized as part of the system. |
