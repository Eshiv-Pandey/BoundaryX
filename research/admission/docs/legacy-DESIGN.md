---
name: "Benchmark review tools"
description: "Local evidence workspaces for inspecting agent handoffs and their saved proof."
colors:
  paper: "#f3f4f7"
  surface: "#ffffff"
  ink: "#24273a"
  muted: "#575b6c"
  line: "#cbcbd1"
  accent: "#3e428c"
  accent-soft: "#e9e9f4"
  accent-hover: "#30346f"
  good: "#24644c"
  good-bg: "#e8f2ec"
  warn: "#7a4e16"
  warn-bg: "#f6ebd7"
  quiet: "#eae8e3"
  fail: "#873943"
  code-surface: "#eef0f5"
  selection: "#d6d5ef"
typography:
  display:
    fontFamily: "Georgia, Cambria, serif"
    fontSize: "clamp(2.1rem, 3.8vw, 3.5rem)"
    fontWeight: 400
    lineHeight: 1.12
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Georgia, Cambria, serif"
    fontSize: "1.7rem"
    fontWeight: 400
    lineHeight: 1.12
  title:
    fontFamily: "Georgia, Cambria, serif"
    fontSize: "1.2rem"
    fontWeight: 400
    lineHeight: 1.12
  body:
    fontFamily: "Segoe UI, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Segoe UI, Arial, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 650
    lineHeight: 1.5
  code:
    fontFamily: "Consolas, monospace"
    fontSize: "0.84rem"
    fontWeight: 400
    lineHeight: 1.55
  benchmark-display:
    fontFamily: "Georgia, Cambria, serif"
    fontSize: "2.25rem"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "normal"
  benchmark-headline:
    fontFamily: "Georgia, Cambria, serif"
    fontSize: "1.55rem"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "normal"
  benchmark-title:
    fontFamily: "Georgia, Cambria, serif"
    fontSize: "1.1rem"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "normal"
rounded:
  tag: "3px"
  code: "4px"
  control: "5px"
spacing:
  compact: "8px"
  item: "12px"
  inset: "16px"
  group: "20px"
  panel: "24px"
  workspace: "32px"
components:
  button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  button-hover:
    backgroundColor: "{colors.accent-soft}"
  button-selected:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  select:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  navigation:
    textColor: "{colors.accent}"
  status-good:
    backgroundColor: "{colors.good-bg}"
    textColor: "{colors.good}"
    rounded: "{rounded.tag}"
    padding: "6px 8px"
  evidence-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    padding: "24px 22px"
  benchmark-evidence-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    padding: "26px 28px"
  code-panel:
    backgroundColor: "{colors.code-surface}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.code}"
    padding: "15px"
  benchmark-code-panel:
    backgroundColor: "{colors.code-surface}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    rounded: "{rounded.code}"
    padding: "16px"
  artifact-table:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
  outcome:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.ink}"
    padding: "10px 12px"
---

# Design System: Benchmark review tools

## Overview

**Creative North Star: "Supervisor evidence workspace"**

The incumbent supervisor replay establishes a restrained reading environment: cool paper, white evidence panels, ink text, purple selection and quiet rules. Regular serif headings give findings a document voice; system UI controls and data keep inspection practical. This is the implemented vocabulary of the local review tools.

This scan covers `demo/supervisor-v1` and its `demo/benchmark-v2` extension. The benchmark retains the existing identity while adding a full-width result matrix and a shared selected-case panel. Its more compact heading sizes, shell width and responsive breakpoints are surface variants, not a replacement of the supervisor system. Saved evidence, original captures and clear outcome labels remain the focus.

**Key Characteristics:**

- Flat white content on cool paper, divided by thin rules.
- Regular Georgia/Cambria findings; Segoe UI controls and data; Consolas captures.
- Purple selection, with separate semantic outcome colors and explicit text labels.
- Locally scrolling evidence, responsive selectors and a print view.

## Colors

The palette uses a subdued purple accent over cool neutral paper. The frontmatter preserves the canonical source values; `surface` normalizes the benchmark's equivalent CSS shorthand to the incumbent's full hex.

### Primary

- **Ink Purple** (`accent`): links, focus outlines, selected controls and the incumbent evidence-panel top rule.
- **Pale Purple** (`accent-soft`): control hover and the benchmark outcome summary.
- **Deep Purple** (`accent-hover`): incumbent primary-action hover.
- **Selection Purple** (`selection`): selected text in both surfaces.

### Secondary

These are semantic outcomes, not additional brand accents.

- **Preserved Green** (`good`, `good-bg`): passing values and incumbent good-status tags.
- **Caution Brown** (`warn`, `warn-bg`): incumbent partial-status and request-error treatments.
- **Missing Red** (`fail`): benchmark missing/changed fields and failed outcome values. The result also appears in text.

### Neutral

- **Cool Paper** (`paper`): page canvas.
- **White Surface** (`surface`): evidence panels, controls and result tables.
- **Reading Ink** (`ink`): main text.
- **Muted Ink** (`muted`): explanations, metadata, field labels and table headers.
- **Quiet Rule** (`line`): section dividers, table rows and control borders.
- **Code Paper** (`code-surface`): JSON blocks and benchmark table headers.
- **Quiet Status** (`quiet`): incumbent unavailable-status backgrounds.

**The Evidence State Rule.** Purple identifies interaction. Outcome colors accompany an explicit status or numerical result rather than replacing it.

## Typography

**Display Font:** Georgia, Cambria, serif.  
**Body Font:** Segoe UI, Arial, sans-serif.  
**Code Font:** Consolas, monospace.

Regular serif findings sit above compact system UI controls and measured data. No font assets or remote font loading are used. The base is (16px); code uses a more generous line height and wraps long identifiers.

### Hierarchy

- **Display:** the incumbent responsive title, regular weight, with the `display` frontmatter token; its line length is capped at (22ch).
- **Headline / Title:** incumbent section and evidence headings use `headline` and `title`. The incumbent case heading is a contextual larger heading (2rem; 1.8rem below 560px).
- **Benchmark headings:** `benchmark-display`, `benchmark-headline` and `benchmark-title` retain the same regular serif voice at a denser scale. Below (620px), the benchmark title is (1.8rem).
- **Body:** inherited `body` token; explanatory paragraphs are limited to (74ch) in the incumbent and (73ch) in the benchmark.
- **Label:** the `label` token records benchmark field labels. Incumbent filter labels are a measured variant (0.8rem, weight 600). Navigation and tables commonly use (0.9rem).
- **Code:** `code` applies to JSON and identifiers; the benchmark phone variant is (0.8rem). Tabular numerals are applied to counts and table data.

**The Two Voices Rule.** Use the serif voice for findings and headings, the system UI voice for controls and data, and the monospace voice for literal evidence.

## Layout

Both surfaces use a centered, fluid shell and a left selector beside an evidence area with `minmax(0, 1fr)`. Thin horizontal rules separate sections. Reused rhythm steps are recorded in frontmatter; their application varies with content rather than forming an invented uniform grid.

The incumbent shell has a maximum width of (1540px) and desktop side insets of (42px). Its workspace is a (235px) sidebar with a (32px) gap. At (1100px), the sidebar becomes (190px) with a (20px) gap. At (800px), selectors move above the content and the case selector becomes a six-column compact grid. Side-by-side comparisons stack below (560px). These are incumbent behaviors.

The benchmark shell has a maximum width of (1440px) and desktop insets of (40px). The result matrix precedes a workspace with a (230px) sidebar, a (32px) gap and evidence-panel padding of (26px 28px). Table cells use (13px 15px) padding. The table has a minimum width of (650px) inside its own overflow container; wide data scrolls locally.

At (900px), benchmark insets become (22px), the sidebar becomes (190px), and the gap becomes (20px). Paired JSON blocks become one column; field checks reduce from three columns to two. At (620px), insets become (16px), the top bar stacks, view buttons stack, selectors move above the panel and panel padding becomes (20px 16px). Run counts remain a two-column grid. JSON block height is capped at (330px) in the benchmark and (370px) in the incumbent, with internal scrolling and long-string wrapping.

Print hides navigation and selectors, removes shell insets and code height caps, and preserves readable evidence. The benchmark keeps two JSON columns in print; the incumbent keeps its two comparison panels.

**The Local Overflow Rule.** Constrain wide tables and captures inside their evidence containers so the page and controls remain usable at narrow widths.

## Elevation & Depth

There are no box shadows. White content, soft status fills, purple state and one-pixel borders provide hierarchy. The incumbent evidence panel adds a one-pixel purple top rule; the benchmark panel stays a plain white surface.

When reduced motion is not requested, the incumbent uses a short background reveal (0.18s, ease-out) and background transitions (0.12s, ease-out). The benchmark uses an outcome background reveal (0.18s, ease-out) and control background transitions (0.16s, ease-out). Motion does not move content. Exact snippets and transient colors live in the sidecar.

**The Flat Surface Rule.** Separate content with the existing one-pixel rules and tonal surfaces; preserve the flat depth vocabulary.

## Shapes

Controls have gently rounded corners (`control`), while JSON uses `code` corners and incumbent status tags use `tag` corners. Evidence panels and tables are rectangular. Borders are solid (1px). Native select arrows and disclosure markers supply familiar affordances.

## Components

### Buttons

Neutral controls use white surfaces, ink text, quiet borders and the shared `button` padding. The incumbent minimum control height is (42px); the benchmark raises it to (44px). Hover uses pale purple. Benchmark view buttons expose selection through `aria-pressed` with purple fill and white text; incumbent case buttons use the same selected colors. The incumbent primary action uses `accent-hover` on hover. Keyboard focus is a (3px) purple outline offset by (3px). Disabled opacity is (0.48) in the incumbent and (0.5) in the benchmark.

### Inputs / Fields

The shipped fields are native selects. They use the control shape, white fill, quiet border and visible labels. Sidebar selects fill their container; benchmark selects use (0.88rem) text. The benchmark adds the same pale-purple hover as buttons. Focus follows the common outline. Do not infer a text-field or validation system from these selects.

### Navigation

The top bar uses a plain brand link and compact text links separated from the page by a quiet rule. Links remain underlined apart from the benchmark brand and gain a thicker underline on hover. The benchmark view controls wrap on desktop and stack on phones. The skip link becomes visible on focus. Footer links wrap as needed.

### Status Tags and Outcomes

Incumbent status tags use compact (6px 8px) padding, regular small corners, weight (650) and explicit text. Good, partial and unavailable variants have their corresponding semantic fills. The benchmark uses a pale-purple outcome strip with (10px 12px) padding and colored, named field states. Selected interaction and pass/fail semantics remain separate.

### Evidence Panels

Incumbent evidence panels are white with the purple top rule and `evidence-panel` padding. The benchmark's `benchmark-evidence-panel` is plain white and contains outcome, field checks, captures and native disclosures. Field checks are a definition list with a quiet bottom rule, muted term and weight (600) result. The live region announces selected-case content.

### Tables and Captured JSON

The benchmark table uses white rows, Code Paper headers, Quiet Rule borders and tabular numerals. Row and column headers retain their semantics. JSON blocks use the monospace token, soft gray-blue background, short corners, wrapped strings and internal overflow. Native disclosure controls reveal additional receipts. Evidence links open the retained capture; selecting a view, case, route or condition changes saved evidence only.

## Do's and Don'ts

### Do:

- **Do** preserve the inherited paper, ink, purple and quiet-rule vocabulary when extending the local review tools.
- **Do** keep findings in regular Georgia/Cambria and controls, labels and data in Segoe UI.
- **Do** label outcomes in words and retain the distinction between selection, success, missing information and unavailable observation.
- **Do** use local overflow for matrices and captures, and move selectors above evidence at each surface's observed phone breakpoint.
- **Do** preserve visible keyboard focus, the skip link, native select behavior and reduced-motion handling.

### Don't:

- **Don't** promote the benchmark's compact heading sizes or breakpoints into replacements for the incumbent supervisor surface.
- **Don't** replace readable status labels with color alone.
- **Don't** turn unused declarations or superseded heading declarations into recommended component styles.
