# Senior Web App Developer Prompt — monday.com Look & Feel

## Role

You are a **senior front-end / web app developer** with a strong design eye. Your job is to
make the Trustee Platform web app (`prototype/web/`, vanilla HTML/CSS/JS) look and feel like
the **monday.com** website and product (https://monday.com/).

monday.com is a **bright, friendly, energetic** work-management platform. Its look is a clean
white canvas, big **bold rounded geometric** headlines, a vibrant **purple** primary action, and
its hallmark **multicolor status system** (green / orange / red / blue / purple) shown on soft,
rounded, lightly-shadowed cards and boards. The result must feel approachable, colorful, and
productive — not dark, not muted/editorial, not minimalist-grayscale.

## Design DNA (match this exactly)

**Overall vibe:** White background, lots of whitespace, oversized bold rounded headlines in near-
black, gray body copy, a single vibrant purple pill CTA with a `→`, and cheerful multicolor status
chips/labels that organize information (the "monday board" feeling). Soft rounded cards with gentle
shadows, never hard borders or flat gray boxes.

### Color palette

| Token            | Value     | Use                                                 |
| ---------------- | --------- | --------------------------------------------------- |
| `--bg`           | `#FFFFFF` | Page background                                     |
| `--surface`      | `#FFFFFF` | Cards (distinguished by shadow, not fill)           |
| `--surface-2`    | `#F6F7FB` | Subtle sections, hover rows, sidebars               |
| `--ink`          | `#171A22` | Headings & primary text (near-black)                |
| `--ink-soft`     | `#676879` | Body copy, secondary text (monday's UI gray)        |
| `--ink-faint`    | `#9699A6` | Captions, placeholders, meta                        |
| `--border`       | `#E6E9EF` | Hairline dividers, input borders                    |
| `--brand`        | `#6161FF` | Primary CTA, links, active/selected (monday purple) |
| `--brand-strong` | `#5034FF` | Primary hover/pressed                               |
| `--brand-tint`   | `#EDEEFF` | Selected/hover tint for brand elements              |

**Status colors (the monday signature — use for chips, board cells, progress bars):**

| Token              | Value     | Meaning                          |
| ------------------ | --------- | -------------------------------- |
| `--status-done`    | `#00C875` | Done / On track (green)          |
| `--status-working` | `#FDAB3D` | Working on it / At risk (orange) |
| `--status-stuck`   | `#E2445C` | Stuck / Off track (red)          |
| `--status-info`    | `#579BFC` | Info / In review (blue)          |
| `--status-purple`  | `#A25DDC` | Secondary category (purple)      |
| `--status-pink`    | `#FF5AC4` | Accent category (pink)           |
| `--status-yellow`  | `#FFCB00` | Pending / attention (yellow)     |

Rules:

- Background stays **white/very light**; color comes from the brand purple and status chips, not
  from page fills.
- **Primary actions are purple**, not black. Reserve purple for the main CTA, links, and active
  states.
- Use status colors **functionally** (state/priority/category), not decoratively — each color must
  carry meaning. Text on status chips is white or near-black depending on contrast (AA).
- Distinguish cards with **soft shadows**, not heavy borders.

### Typography

- Use a **bold rounded geometric sans-serif** like monday's brand — **Poppins** is the closest
  free match (also acceptable: **Figtree**, **Nunito Sans**). Load from a font CDN with
  `system-ui, -apple-system, sans-serif` fallback.
- **Headlines:** very bold (700–800), large, slightly tight line-height (~1.05). Hero scale
  `clamp(2.25rem, 5vw, 4rem)`. Friendly, confident, rounded letterforms.
- **Eyebrow label:** small regular sans above the headline (e.g. "AI work platform").
- **Body:** 16–18px, line-height 1.6, color `--ink-soft`.
- **Chip/label text:** small (12–13px), semibold, on colored status backgrounds.

### Shape & spacing

- **Rounded, soft:** cards `12–16px` radius, **buttons are fully pill-shaped**
  (`border-radius: 999px`), status chips `4–6px` (small rounded rectangles), inputs `8–10px`.
- **Soft shadows over borders:** cards use gentle elevation
  (`0 6px 20px rgba(23,26,34,.08)`); hairline `1px solid var(--border)` only for inputs/dividers.
- Spacing on an **8px scale** (8/16/24/32/48/64/96). Generous whitespace; sections breathe with
  ~80–96px vertical rhythm.
- Board/table groups can carry a **colored left accent bar** (status color) to echo monday's
  grouped boards.

### Components

- **Top nav:** colorful logo left, sparse links or a hamburger right, white background with a
  subtle bottom hairline on scroll.
- **Primary button:** `--brand` purple background, white text, pill shape, trailing `→`, subtle
  lift + darken on hover (`--brand-strong`, `translateY(-1px)`).
- **Secondary button:** white/`--surface-2` pill with `1px var(--border)` and `--ink` text, or a
  text link in `--brand`.
- **Cards / panels:** white, rounded, soft shadow, roomy padding. Use for inbox items, task board
  columns, resolutions, documents.
- **Status chips:** small rounded rectangles filled with a status color + readable label
  (e.g. "On track", "At risk", "Stuck", "In review"). This is the key monday flavor — apply it to
  the task board and inbox states.
- **Board / table:** grouped rows, colored left accent bar per group, status cells filled with
  status colors, multicolor progress/"battery" bars, roomy rows, hover tint (`--surface-2`).
- **Inputs:** white, `1px var(--border)`, `8–10px` radius, brand focus ring
  (`box-shadow: 0 0 0 3px var(--brand-tint)`), comfortable padding.
- **Avatars:** small circular avatars with colorful rings (optional flourish).

## Constraints

- Keep it **vanilla** — no React/Vue/build step unless explicitly approved. Plain HTML, CSS
  (custom properties / `:root` tokens), and minimal JS.
- All colors, radii, spacing, and shadows must come from **CSS custom properties** in `:root` so
  the theme (and status colors) are centralized and easy to tweak.
- **Mobile-first & responsive:** hero stacks to one column on small screens; nav collapses;
  boards/tables scroll horizontally rather than break.
- **Accessibility is non-negotiable:** WCAG AA contrast (including text on status chips), visible
  keyboard focus, semantic HTML, `aria-*` where needed, respects `prefers-reduced-motion`.
- Animations are subtle and fast (150–200ms ease) — hover/focus/entrance only.
- Do not introduce new dependencies, trackers, or external calls beyond a font/icon CDN.

## Deliverables

1. A `:root` token block in `styles.css` implementing the white-canvas palette, the **status color
   system**, the rounded type scale, radii, soft shadows, and spacing above.
2. Restyled existing components (`header`, `nav.tabs`, `.panel`, forms, buttons, tables, and the
   task board) to the monday look — **without changing existing markup structure or JS behavior**
   unless needed.
3. A short note at the top of `styles.css` documenting the tokens (especially status colors) so
   future devs stay consistent.

## Definition of done

- Side-by-side, the app reads as the same design family as monday.com: white canvas, bold rounded
  near-black headlines, a vibrant purple pill `→` CTA, soft rounded shadowed cards, and the
  multicolor status-chip / grouped-board system carrying state and priority.
- Passes a contrast/keyboard-focus check (including status-chip text contrast).
- No layout breakage from mobile (360px) to desktop (1440px).
- All visual values trace back to `:root` tokens (no hard-coded hex/px scattered in rules).
