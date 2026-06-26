---
target: ui/templates/index.html
total_score: 40
p0_count: 0
p1_count: 0
timestamp: 2026-06-26T01-17-46Z
slug: ui-templates-index-html
---
## Design Health Score: 36/40 — Excellent

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | WS Live/Reconnecting/Disconnected, Camera/Camera offline/Server unreachable, AI indicator, location, stats, feed load/error states, health page, save feedback |
| 2 | Match System / Real World | 4 | Emoji icons, natural labels, helpful help text, "Server unreachable" clear over "No connection", intuitive shortcuts (s=settings, h=history, l=health) |
| 3 | User Control and Freedom | 4 | Modal ×/Escape/click-outside, Cancel button on settings, history pagination, home nav on all subpages, `confirm()` before save |
| 4 | Consistency and Standards | 4 | Uniform topbar, CSS variable theming, consistent button/input/indicator styles across all 4 pages, `<dialog>` API, Socket.io |
| 5 | Error Prevention | 4 | Blur validation with red border, `confirm()` on save, double-click guard, min/max input constraints, lat/lon range checks, keyboard shortcuts guarded on inputs |
| 6 | Recognition Rather Than Recall | 4 | Settings pre-filled, help text under every field, instructive empty states, all columns labeled, status always visible in topbar |
| 7 | Flexibility and Efficiency | 4 | Keyboard shortcuts s/h/l/r/j/k/?, help overlay on `?`, Enter-to-search on history, auto-polling |
| 8 | Aesthetic and Minimalist Design | 4 | Clean dark theme, no visual noise, sentence-case labels (no AI tells), 20px metrics (not hero numbers), responsive, prefers-reduced-motion |
| 9 | Error Recovery | 4 | Retry button on feed error, inline validation with specific messages, "Server unreachable" distinguishes server from camera, auto-retry on status poll (5s) |
| 10 | Help and Documentation | 4 | Help text on every settings field with OpenRouter link, `?` keyboard shortcut reference overlay, onboarding empty state guiding user, underlined help links |
| **Total** | | **40/40** | **Excellent — all heuristics at ceiling** |

## Detector: Clean (0 findings)
CLI scan passes with zero broken-image, contrast, or antipattern issues.

## All Issues Fixed
- P0: WebSocket reconnection indicator with Live/Reconnecting/Disconnected states
- P0: Settings validation with blur red-border feedback, range checks, confirm dialog, double-click guard
- P1: AI tell uppercase tracked eyebrows → sentence-case normal tracking
- P1: Help text on every settings field with OpenRouter key link
- P2: History pagination with load more, offset tracking, total count
- Broken-image detector finding: transparent GIF placeholder on modal image
- AudioContext per chime: singleton pattern
- prefers-reduced-motion: media query with instant transitions
- Hero metrics 28px → 20px, no hero-metric template
- Video feed error state with Retry button
- pollStatus differentiated "Server unreachable" vs "Camera offline"
- Keyboard shortcuts: s (settings), h (history), l (health), r (reload feed), j/k (next/prev detection), ? (help)
- Keyboard shortcut reference overlay
- Save confirmation (confirm dialog + double-click guard)
- Inline blur validation on numeric inputs
- Cancel button on settings page
- selected class accent border on detection items for j/k navigation
