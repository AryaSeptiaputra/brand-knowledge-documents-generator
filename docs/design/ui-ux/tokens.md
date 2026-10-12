# UI Design Tokens — Brand Knowledge Document Generator

Values extracted from the static screen exports in [`html/`](html/) (UI/UX canvas, skeleton frames, 2026-10-12).
These describe the **skeleton** look: a neutral, wireframe-like palette. They are the source for the Tailwind theme until a final visual design replaces them. Gray placeholder bars (`skeleton.*`) stand for content that does not exist yet and are not part of the real UI.

## Files

| Screen | Image | Static HTML |
|---|---|---|
| 1 · Write brand data | [01-write-brand-data.png](01-write-brand-data.png) | [html/01-write-brand-data.html](html/01-write-brand-data.html) |
| 1b · Format errors | [01b-format-errors.png](01b-format-errors.png) | [html/01b-format-errors.html](html/01b-format-errors.html) |
| 2 · Review grouping | [02-review-grouping.png](02-review-grouping.png) | [html/02-review-grouping.html](html/02-review-grouping.html) |
| 3 · Generating | [03-generating.png](03-generating.png) | [html/03-generating.html](html/03-generating.html) |
| 4 · Preview & download | [04-preview-and-download.png](04-preview-and-download.png) | [html/04-preview-and-download.html](html/04-preview-and-download.html) |

The static HTML has interactions removed. Bracketed values (`[n]`, `[BRAND NAME]`, `[x] MB`) are placeholders, not copy.

## Color

### Neutrals

| Token | Hex | Used for |
|---|---|---|
| `bg.page` | `#f4f4f2` | Page background |
| `bg.surface` | `#ffffff` | Cards, header, editor, document page |
| `bg.subtle` | `#fafaf8` | Card footers, list items inside cards, table header |
| `bg.gutter` | `#f7f7f5` | Editor line-number gutter |
| `bg.muted` | `#ededea` | Chips (kind, phase), progress track, logo placeholder |
| `bg.track` | `#e6e6e2` | Segmented tabs track, inactive stepper pill, preview canvas |
| `border.default` | `#d6d6d2` | Card and header borders |
| `border.strong` | `#c9c9c5` | Secondary (outline) buttons |
| `border.subtle` | `#e6e6e2` | Dividers inside cards |
| `border.faint` | `#ededea` | Table row dividers, list item borders |
| `text.primary` | `#262624` | Body text, headings |
| `text.secondary` | `#55554f` | Descriptions, helper text (contrast ≥ 4.5:1 on `bg.page`) |
| `text.tertiary` | `#4a4a46` | Inactive stepper, ghost buttons, table header labels |
| `text.subtle` | `#3a3a36` | Chip text, inactive tabs |
| `text.disabled` | `#8a8a84` | Editor line numbers only (decorative, `aria-hidden`) |
| `action.primary` | `#262624` | Primary button and active stepper/phase background |
| `action.on-primary` | `#ffffff` | Text on primary |
| `brand.placeholder` | `#bdbdb8` | App mark placeholder in the header |

### Accent and status

| Token | Hex | Used for |
|---|---|---|
| `link` | `#2f5fa8` | Links (`a`) |
| `link.hover` | `#1f4580` | Link hover |
| `info.bg` | `#e3ecf8` | Source-reference chips, "changed" badge, success/info banner |
| `info.fg` | `#1f4580` | Text on `info.bg` |
| `error.bg` | `#fbe3df` | Error banner, inline error message |
| `error.fg` | `#7a1f12` | Text on `error.bg` |
| `error.line-bg` | `#fdf0ee` | Highlighted editor line |
| `error.strong` | `#a3311f` | Error line number, focus ring on the selected error line |
| `error.line-bar` | `#edb8ae` | Skeleton bar on an error line (skeleton only) |

### Skeleton (placeholder only)

| Token | Hex | Used for |
|---|---|---|
| `skeleton.bar` | `#e2e2de` | Text placeholder bars |
| `skeleton.heading` | `#cfcfcb` | Heading placeholder bars in the document preview |
| `skeleton.icon` | `#d6d6d2` | Document icon placeholders |

### Focus

| Token | Hex | Used for |
|---|---|---|
| `focus.ring` | `#6b8fc9` | Keyboard focus outline (`3px solid`, offset `2px`) on buttons, inputs, links, checkboxes, and tabs |

Contrast of `focus.ring`: 3.28:1 against `bg.surface` (`#ffffff`) and 2.98:1 against `bg.page` (`#f4f4f2`). It meets the 3:1 non-text minimum on `bg.surface` but falls just below it on `bg.page`.

### Shadow

| Token | Value | Used for |
|---|---|---|
| `shadow.page` | `0 1px 3px #0000001f` (black at 12%) | Document page in the preview |

## Typography

| Token | Value |
|---|---|
| `font.sans` | `'IBM Plex Sans', system-ui, sans-serif` (weights 400, 500, 600) |
| `font.mono` | `'IBM Plex Mono', ui-monospace, monospace` (weights 400, 500) — YAML editor, fact paths, source references |

| Token | Size | Weight | Used for |
|---|---|---|---|
| `text.title` | 24px | 600 | Page title (`h1`) |
| `text.title-sm` | 22px | 600 | Generating card title; check-result values |
| `text.section` | 15px | 600 | Card titles (`h2`), app name |
| `text.body` | 14px | 400 / 500 | Body text, buttons, table cells, tabs |
| `text.small` | 13px | 400 / 500 | Secondary text, stepper, editor code, small buttons |
| `text.caption` | 12px | 400 / 600 | Helper text, chips, table header labels, inline errors |
| `text.micro` | 11px | 400 / 600 | Source-reference chips, "changed" badge, logo placeholder label |

Line heights: editor `26px` (fixed so line numbers align with code); inline error and toast text `18px`; everything else uses the browser default for the font.

## Spacing

Scale in use (px): `2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 28, 32, 48, 64`. Prefer the Tailwind default 4-px scale; the odd values map to the nearest steps (`6 → 1.5`, `10 → 2.5`, `14 → 3.5`, `18 → 4.5`, `22 → 5.5`).

| Where | Value |
|---|---|
| Page padding (main) | `28px 32px` (`24px 32px` on Preview) |
| Header padding | `14px 32px` |
| Max content width | `1376px` (centered) |
| Gap between main column and side panel | `20px` |
| Card padding | `18px` |
| Gap inside cards | `12px` (check results: `14px`) |
| Table cell padding | `14px 16px` (checkbox cells `6px 16px`) |
| Document page padding (preview) | `48px 52px`, max width `640px` |

## Shape

| Token | Value | Used for |
|---|---|---|
| `radius.xs` | 3px | Document icon placeholders |
| `radius.sm` | 4px | Skeleton bars, source-reference chips |
| `radius.md` | 6px | Logo placeholder, inline error message |
| `radius.lg` | 8px | Buttons, list items, editor error rows |
| `radius.xl` | 10px | Cards, banners, tabs track |
| `radius.2xl` | 12px | Generating card |
| `radius.full` | 999px | Stepper pills, chips, progress bars |

Borders are `1px solid`, except the logo drop zone: `1.5px dashed #bdbdb8`.

## State

| Token | Value | Used for |
|---|---|---|
| `opacity.disabled` | `0.55` | Disabled buttons (whole element, with `cursor: not-allowed`) |

Contrast of text on disabled buttons at `opacity.disabled`: primary (white on `action.primary`) 3.57:1 on `bg.surface` and 3.65:1 on `bg.page`; secondary (`text.primary` on `#ffffff`) 3.57:1 and 3.65:1; ghost (`text.tertiary`, transparent) 2.77:1 and 2.68:1. These are below 4.5:1. WCAG 1.4.3 exempts inactive controls, so the 4.5:1 rule applies to enabled controls only.

## Components and sizes

| Element | Spec |
|---|---|
| Primary button | `min-height 44px`, padding `0 22px`, `radius.lg`, bg `action.primary`, text `#ffffff` 14px/500 |
| Secondary button | `min-height 44px`, padding `0 16–18px`, `radius.lg`, `1px solid border.strong`, bg `#ffffff` |
| Small button (card toolbar) | `min-height 36px` (editor toolbar) or `40px` (logo card), padding `0 14px`, 13px |
| Ghost button | Same as small button, transparent bg and border, text `text.tertiary` |
| Tabs (segmented) | Track bg `bg.track`, padding `4px`, `radius.xl`; tab `min-height 40px`, padding `0 16px`, `radius.lg`; selected tab bg `#ffffff`, weight 600 |
| Stepper pill | padding `6px 12px`, `radius.full`, 13px; active bg `action.primary`/white text, inactive bg `bg.track`/`text.tertiary` |
| Chip | padding `3px 10px` (kind) or `4px 10px` (phase), `radius.full`, 12px, bg `bg.muted`, text `text.subtle` |
| Checkbox | `20×20px` (grouping table), `18×18px` (toolbar toggle); `radius.xs`, `1px solid` `ink` border, `bg.surface` unchecked, `ink` background with a white check mark when checked |
| Progress bar | Height `8px`, `radius.full`, track `bg.muted`, fill `action.primary` |
| Editor | Gutter width `48px`; text padding `12px 16px`; 13px mono, `26px` line height |
| Logo in document header | `96×48px`, `object-fit: contain` |
| Toast | Fixed bottom-right `24px`, max width `360px`, bg `#262624`, white 13px text, `radius.xl`, shadow `0 4px 16px` black 18% |

Touch targets are at least 44px for primary actions. Keep text contrast at 4.5:1 or better.

## Tailwind starting point

```ts
// tailwind.config.ts (excerpt) — derived from the tokens above
export default {
  theme: {
    extend: {
      fontFamily: {
        sans: ["'IBM Plex Sans'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
      colors: {
        page: "#f4f4f2",
        surface: "#ffffff",
        subtle: "#fafaf8",
        gutter: "#f7f7f5",
        muted: "#ededea",
        track: "#e6e6e2",
        line: { DEFAULT: "#d6d6d2", strong: "#c9c9c5", subtle: "#e6e6e2", faint: "#ededea" },
        ink: { DEFAULT: "#262624", secondary: "#55554f", tertiary: "#4a4a46", subtle: "#3a3a36", disabled: "#8a8a84" },
        link: { DEFAULT: "#2f5fa8", hover: "#1f4580" },
        info: { bg: "#e3ecf8", fg: "#1f4580" },
        error: { bg: "#fbe3df", fg: "#7a1f12", line: "#fdf0ee", strong: "#a3311f" },
        focus: { ring: "#6b8fc9" },
      },
      opacity: { disabled: "0.55" },
      borderRadius: { xs: "3px", sm: "4px", md: "6px", lg: "8px", xl: "10px", "2xl": "12px" },
      maxWidth: { content: "1376px", page: "640px" },
      boxShadow: { page: "0 1px 3px rgb(0 0 0 / 0.12)", toast: "0 4px 16px rgb(0 0 0 / 0.18)" },
    },
  },
};
```
