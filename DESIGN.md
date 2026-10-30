---
name: CareCompass
description: A calm field-notes journal for noticing personal wellbeing over time.
colors:
  ground: "#F4F8F5"
  surface: "#FFFFFF"
  surface-soft: "#EAF2EC"
  border: "#D7E4DA"
  ink: "#24352B"
  muted: "#52645A"
  sage: "#4E7660"
  sage-dark: "#365B48"
  amber: "#755515"
  coral: "#7A2D30"
  blue: "#365F82"
  green: "#325D48"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "28px"
    fontWeight: 620
    lineHeight: 1.22
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "-0.015em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.62
    letterSpacing: "normal"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "normal"
rounded:
  panel: "18px"
  control: "12px"
spacing:
  page-desktop: "36px"
  page-mobile: "16px"
  control-height: "44px"
components:
  button-primary:
    backgroundColor: "{colors.sage}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "44px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "16px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "44px"
---

# Design System: CareCompass

## Overview

**Creative North Star: “The Field Notes Journal”**

CareCompass is a light, quiet place for an individual to record how they are doing and revisit dated observations. The visual voice is personal and grounded: clean white panels sit on a soft sage-tinted ground, while restrained green accents help people find the next step without making the interface feel clinical or urgent by default.

Use a clear app-scale hierarchy, readable explanatory copy, and small line icons only where they aid recognition. Results are screening categories and personal observations, never a diagnosis or a measure of progress. Keep support and safety language visible and plain. The palette is light-only; do not introduce a dark theme.

**Key Characteristics:**
- Soft sage accents on clean white and ivory-green surfaces.
- Dated, observational language for personal records and screening history.
- Calm, concise next steps with safety guidance preserved.
- One consistent inline SVG line-icon system; no emoji.
- Short, purposeful route and assessment transitions that honor reduced-motion preferences.

## Colors

The palette pairs muted sage with warm-leaning green neutrals; amber, coral, and blue are reserved for meaningful status communication.

### Primary
- **Field Sage** (#4E7660): Primary actions, active navigation, and key interactive accents.
- **Deep Sage** (#365B48): Emphasis, icon strokes, links, and stronger interactive states.

### Secondary
- **Quiet Amber** (#755515): Higher-strain status and caution communication, paired with explicit text.
- **Measured Blue** (#365F82): Informational or moderate-status communication, paired with explicit text.
- **Grounded Green** (#325D48): Positive or steady status, paired with explicit text.
- **Muted Coral** (#7A2D30): Urgent support status; always preserve accompanying support language.

### Neutral
- **Ivory Ground** (#F4F8F5): Main page background; the sole light theme canvas.
- **Paper White** (#FFFFFF): Main content panels and controls.
- **Sage Wash** (#EAF2EC): Soft secondary surface, active-state fill, and quiet callouts.
- **Leaf Border** (#D7E4DA): Panel edges, dividers, and low-emphasis control borders.
- **Forest Ink** (#24352B): Main text and headings.
- **Soft Bark** (#52645A): Supporting copy, labels, and captions.

**The Observation Rule.** Color may distinguish status, but never imply that a screening category is a diagnosis or proof of personal progress.

## Typography

**Display Font:** System sans-serif (`-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, sans-serif)
**Body Font:** System sans-serif (same stack)
**Label/Mono Font:** No separate mono face is established.

**Character:** Compact, practical, and readable. Headings use modest weight and slight negative tracking; body copy stays open enough for reflective prompts and safety explanations.

### Hierarchy
- **Display** (620, 28px desktop / 23.7px mobile, 1.22): App page title and personal greeting.
- **Headline** (600, 20px, 1.35): Section and sub-section headings.
- **Title** (600, about 16px, 1.4): Card and recommendation titles.
- **Body** (400, 16px, 1.62): Questions, records, and explanatory copy; keep line lengths comfortable.
- **Label** (600, 13px, 1.45): Short section labels, field labels, and status captions.

**The Plain-Language Rule.** Screening labels and observations use accompanying plain-language context; typography must not create clinical authority the product does not have.

## Layout

The app uses one centered content column with a maximum width of 1180px. Desktop content padding is 36px horizontally, with 36px above and 72px below; at widths up to 900px this reduces to 22.4px horizontal padding, and at 640px and below it becomes 16px horizontal padding. The mobile type scale reduces the main title to 23.7px. At the narrow breakpoint, horizontal column groups stack into full-width rows. This responsive behavior is specified from CSS; no visual mobile verification is claimed.

Keep the page title and its short explanatory line together. Present histories as dated observations, with the comparison period and categories explicit. Assessment progress should show the current question and total, so the sequence remains legible without relying on color alone.

## Elevation & Depth

The system is flat by default. White and pale sage tonal surfaces, fine leaf borders, and spacing establish hierarchy; bordered containers have no shadow. Use depth sparingly and do not add decorative floating layers.

## Shapes

Use soft, consistent corners rather than pill-shaped panels. Main bordered panels use an 18px radius; controls use 12px. Small status badges and progress segments may use pill shapes where their compact semantic role calls for it. Borders stay thin and low contrast against the pale surfaces.

## Components

Components should feel steady and approachable, with clear labels and visible keyboard focus.

### Buttons
- **Shape:** Soft control corners (12px), minimum height 44px.
- **Primary:** Field Sage fill (#4E7660), white text, compact label typography.
- **Hover / Focus:** Deep Sage hover; a visible 3px focus outline with 2px offset.
- **Secondary / Ghost:** White or transparent surface with a leaf-border stroke; hover uses a subtle pale fill.

### Cards / Containers
- **Corner Style:** 18px for primary bordered panels; selected metric and status surfaces use 14px.
- **Background:** Paper White or Sage Wash on Ivory Ground.
- **Shadow Strategy:** No shadow; use the border and tonal contrast.
- **Border:** 1px Leaf Border on bordered containers.
- **Internal Padding:** Standard panels follow the Streamlit container spacing; compact cards use about 16px.

### Inputs / Fields
- **Style:** White input surface, pale green-gray border, 12px radius; text areas use 14px corners.
- **Focus:** 3px sage-tinted outline with 2px offset.
- **Error / Disabled:** Keep the existing explicit status text and contrast; do not communicate state by color alone.

### Navigation
- **Style:** A labeled sidebar is the signed-in navigation surface. Current destination gets a pale sage fill and stronger text; inactive items remain quiet. Use the same inline SVG line-icon family throughout.

### Signature Components
- **Assessment progress:** A 21-step segmented track, with text stating the question count; the active and completed steps use progressively stronger sage.
- **Status badge:** Short text label on a pale status tint, optionally followed by a dated caption. Always pair color with words.
- **Field note history:** Dates anchor each screening record and check-in. Assessment-history comparisons describe observed categories only, not diagnosis or progress.

## Do's and Don'ts

### Do:
- **Do** use the light-only ivory, white, and sage surface system.
- **Do** keep CareCompass safety, consent, privacy, and non-diagnostic language clear and intact.
- **Do** describe history in dated, observational terms and compare result categories explicitly.
- **Do** pair status colors with readable labels and keep calm next steps easy to find.
- **Do** use one accessible inline SVG line-icon family and no emoji.
- **Do** keep route and assessment motion short and respect `prefers-reduced-motion`.

### Don't:
- **Don't** use dark surfaces, emoji, or a second competing icon style.
- **Don't** present categories as diagnoses, treatment advice, or evidence of progress.
- **Don't** use color alone to communicate urgency, severity, selection, or validation.
- **Don't** alter scoring, safety behavior, consent, persistence, or data handling through visual work.

