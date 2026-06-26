---
target: ui/templates/index.html
total_score: 25
p0_count: 2
p1_count: 2
timestamp: 2026-06-26T01-07-32Z
slug: ui-templates-index-html
---
## Design Health Score: 25/40 — Acceptable

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | WebSocket failure is silent — no "disconnected" state shown |
| 2 | Match System / Real World | 4 | Clean emoji+label pairs, natural timestamps |
| 3 | User Control and Freedom | 3 | Modal dismiss via 3 methods ✅; settings has no undo |
| 4 | Consistency and Standards | 3 | Same chrome across pages ✅; settings uses inline styles; history vs health use different visual languages |
| 5 | Error Prevention | 2 | Settings: API key unvalidated, port accepts negatives, no confirm before overwriting live config |
| 6 | Recognition Rather Than Recall | 4 | Plates, times, status all visible at a glance |
| 7 | Flexibility and Efficiency | 2 | No keyboard shortcuts, no batch ops, no search on live list |
| 8 | Aesthetic and Minimalist Design | 3 | Uppercase 11px labels (AI tell), 28px hero numbers, slide-in animation contradicts "calm" goal |
| 9 | Error Recovery | 1 | WebSocket silently returns null; settings shows "Failed" with no fix; health catches with dead message |
| 10 | Help and Documentation | 0 | Zero tooltips, zero help, "Dedup Window" is jargon, model names cryptic |
| **Total** | | **25/40** | **Acceptable — significant improvements needed** |

## Anti-Patterns Verdict

**LLM assessment:** Barely passes AI slop test, but only because the project is genuinely small, not because it avoids the tells. The tiny uppercase tracked eyebrow pattern (`.health-label`, `.modal-info-label`: 11px, uppercase, 0.5px tracking) is the most recognizable AI-generation fingerprint. The health-page metric cards (28px bold monospace over tiny label) land squarely in the hero-metric template zone.

**Deterministic scan:** 1 finding — `broken-image` on `index.html:68`: the modal `<img>` has an empty `src=""` attribute.

**Visual overlays:** Not available — no browser runtime present to execute injection.

## Overall Impression

A functional dashboard with a dark theme that fits the brief, but held back by missing error recovery, zero help documentation, and several detectable AI pattern tells. The modal interaction is genuinely polished; the settings page is the weakest surface.

## What's Working

1. **Restrained dark palette matches the brief.** `--bg: #0a0a0f` / `--surface: #14141e` / `--accent: #4ade80` creates the "well-lit room at night" atmosphere PRODUCT.md asks for.
2. **Modal interaction is fully baked.** Three close methods (X, backdrop click, Escape), body scroll lock, clean dataset passing.
3. **Responsive layout with real thought.** The flex-direction swap at 768px, detections-panel at 40vh, and 480px modal breakpoint show considered phone usage.

## Priority Issues

### P0 — Silent WebSocket failure (`app.js:17-27`)
**Why:** System runs unattended for hours. If socket dies, dashboard freezes silently. Violates "Reliability first" from PRODUCT.md.
**Fix:** Reconnection indicator in topbar, auto-retry with exponential backoff, show last-known-good timestamp.
**Command:** `/impeccable harden`

### P0 — Settings save has no validation or rollback (`settings.html:98-121`)
**Why:** Port `-1`, API key `""`, or corrupt resolution can brick remote access on next restart.
**Fix:** Input validation (port ≥1024 ≤65535, API key format, numeric bounds). Confirm step. Store last working config.
**Command:** `/impeccable harden`

### P1 — Tiny uppercase tracked eyebrows (`.health-label`, `.modal-info-label`)
**Why:** The single most identifiable AI-generation pattern. Undermines trust.
**Fix:** Replace with sentence-case, normal letter-spacing, 12px weight 600. Or use leading icons.
**Command:** `/impeccable quieter` / `/impeccable typeset`

### P1 — Zero help or documentation anywhere
**Why:** "Dedup Window" is jargon. Sensitivity slider has no labels. API key placeholder doesn't explain where to get one.
**Fix:** Inline help text (title attrs, helper spans), brief onboarding paragraph on dashboard, "Learn more" links.
**Command:** `/impeccable clarify`

### P2 — No pagination on history, capped at 200 rows (`history.html:46`)
**Why:** After a week of operation, 200 rows could be one day. Can't see older data.
**Fix:** Load more / infinite scroll, server-side pagination, row count indicator.
**Command:** `/impeccable harden`

## Persona Red Flags

**Alex (Power User):** Zero keyboard shortcuts beyond Escape. No batch operations. No data export. History search is plate-only.

**Jordan (First-Timer):** "Starting..." on first load with no expected duration. 14 settings fields with unexplained labels. No welcome or guidance — dashboard just sits there.

**Casey (Mobile):** Hardcoded inline widths on settings inputs (`style="width:100px"`). Landscape phone not considered (568-812px wide falls in gap between mobile and desktop breakpoints).

## Minor Observations
- `AudioContext` created per chime — Chrome caps at ~6, chime silently stops
- No `prefers-reduced-motion` for `slideIn` animation
- No `@supports` guard on `backdrop-filter: blur(4px)`
- 🚗 emoji renders differently across platforms
- Settings lacks a back button (only home icon)

## Questions to Consider
1. Single 880Hz chime for 350ms — in a quiet carpark at 3am, does this alert you or wake the neighborhood?
2. Detection list caps at 100 with silent eviction — should it show "99+ earlier today" after eviction?
3. Settings changes while camera is recording — does the system handle gracefully?
