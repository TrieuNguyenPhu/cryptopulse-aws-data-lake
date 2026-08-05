---
name: CryptoPulse
description: Local crypto market intelligence presented as a clear operational route.
colors:
  route-yellow: "#f7c948"
  ink: "#111111"
  warm-paper: "#f4f1e8"
  surface: "#ffffff"
  muted: "#5f625f"
  divider: "#c9c7be"
  positive-on-dark: "#45d483"
  negative-on-dark: "#ff6973"
typography:
  headline:
    fontFamily: "Segoe UI, Frutiger, Arial, sans-serif"
    fontSize: "clamp(2rem, 3vw, 2.75rem)"
    fontWeight: 750
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Segoe UI, Frutiger, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
  label:
    fontFamily: "Segoe UI, Frutiger, Arial, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 700
    letterSpacing: "0.04em"
rounded:
  control: "4px"
  board: "12px"
spacing:
  compact: "0.75rem"
  standard: "1rem"
  section: "2rem"
components:
  action-primary:
    backgroundColor: "{colors.route-yellow}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "2.7rem"
  route-board:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.board}"
    padding: "1rem 1.2rem 1.1rem"
  data-table:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.board}"
---

# Design System: CryptoPulse

## Overview

**Creative North Star: "Terminal Wayfinding"**

CryptoPulse behaves like a calm chain of operational decisions: verify provenance, choose a
destination, narrow the market, read breadth, then inspect rows. The visual world borrows the
clarity of transit signage without imitating a physical sign or adding decorative infrastructure.

The interface is dense and task-first. Matte ink surfaces establish state, warm paper supports
long sessions, and terminal yellow appears only where the user needs direction or focus.

**Key Characteristics:**

- Provenance is visible before analysis.
- Continuous boards replace isolated metric cards.
- Dense tables carry the detail; decoration never competes with them.
- One brief clip reveal is the only authored motion.

## Colors

The palette uses one directional accent, two market-state colors, and quiet operational neutrals.

### Primary

- **Terminal Yellow:** Marks selected navigation, focus, warnings, and the primary filter action.

### Neutral

- **Matte Ink:** Frames provenance, filters, and breadth as connected operational surfaces.
- **Warm Paper:** Keeps the full-page canvas softer than pure white.
- **Data Surface:** Holds the high-density table and native controls.
- **Muted Signal:** Carries supporting copy and freshness detail.
- **Measured Divider:** Separates rows and board cells without becoming ornament.

### Named Rules

**The Direction-Only Yellow Rule.** Yellow identifies a decision, focus target, or warning; it is
not a general decoration color.

**The State-on-Dark Rule.** Positive and negative colors appear inside the dark breadth board,
where they remain subordinate to the directional accent.

## Typography

**Body Font:** Segoe UI with Frutiger, Arial, and generic sans-serif fallbacks.

**Character:** A workhorse humanist sans keeps labels and financial columns familiar. Scale and
weight create hierarchy; the interface does not introduce a separate promotional display voice.

### Hierarchy

- **Headline:** Compact route titles, large enough to anchor a surface but never treated as a hero.
- **Section title:** Medium-weight analytical grouping labels.
- **Body:** Native control labels, captions, and data presentation at normal reading size.
- **Label:** Uppercase board labels with modest tracking for quick scanning.

### Named Rules

**The Workhorse Type Rule.** Type prioritizes legibility and column scanning over brand theater.

## Layout

The main canvas is wide and capped at 1480px. Provenance, destination, filters, breadth, and results
form one vertical route. Summary boards use equal-width cells; the breadth board gives its heading
and final ratio more room. At 900px and below, provenance wraps, boards become single columns,
section headings stack, and the table retains horizontal scrolling.

Spacing follows a compact operational rhythm: small gaps inside controls, standard spacing inside
boards, and larger breaks only between analytical sections.

## Elevation & Depth

The system is flat by default. Black and white tonal layers plus fine dividers carry hierarchy.
Only the large data surface receives a soft ambient shadow; boards use a yellow border instead of
stacking border and shadow.

**The One-Depth Cue Rule.** A surface uses either a structural border or an ambient shadow, never
both as decoration.

## Shapes

Inputs and action controls use compact 4px corners. Analytical boards and tables use measured 12px
corners. The recurring silhouette is a long horizontal route board divided into data cells; pills,
floating bubbles, and ornamental clipping are absent.

## Components

### Buttons

- **Primary:** Terminal yellow on matte ink, full control width inside the filter form.
- **Shape:** Compact corners and a minimum height of 2.7rem.
- **Focus:** A visible yellow outline with separation from the control edge.

### Cards / Containers

- **Route board:** Matte ink, yellow structural border, white detail, and yellow primary figures.
- **Data table:** White surface with one soft ambient shadow and dense rows.
- **Internal padding:** Standard board spacing; no nested card stacks.

### Inputs / Fields

- **Style:** Native Streamlit fields grouped on one dark filter surface.
- **Focus:** A three-pixel terminal-yellow outline.

### Navigation

Two wide destination choices act as route signs. The active destination owns the yellow field;
inactive destinations remain neutral and readable. On small screens, the control stays direct
rather than collapsing into a hidden menu.

### Breadth Board

Gainers, unchanged assets, losers, and market breadth read as one continuous state. Vertical rules
become horizontal rules on narrow screens, preserving order and scanability.

## Do's and Don'ts

### Do:

- **Do** show source freshness and local-data status before analytical content.
- **Do** use yellow sparingly for direction, focus, and warning.
- **Do** prefer one continuous board when several metrics describe the same market state.
- **Do** preserve dense, horizontally scrollable tables on small screens.

### Don't:

- **Don't** introduce crypto-neon gradients, glass effects, or generic floating KPI cards.
- **Don't** imply real-time data, auto-refresh, or investment guidance.
- **Don't** add decorative icons, badges, or animation without a functional state to communicate.
- **Don't** create a new component layer until repeated UI patterns justify one.
