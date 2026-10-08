# Dynamic settings panel + Activity Log — 2026-10-08 (unreleased)

## Problem (user report)
- Subtitles box squashed into a thin strip on the user's window size (confirmed
  via Q&A: left panel has no scroll area, Qt compresses last boxes).
- Activity Log hard-capped at 100 px → only 2–3 visible lines ("text crowded").
- Screenshot not readable by agent; answers captured in brainstorm session
  (mockups: .superpowers/brainstorm/80749-1791454498/content/).

## Changes
1. Left panel wrapped in QScrollArea (`self.settings_scroll`) — boxes always
   keep natural height; horizontal splitter (300/950) unchanged. Size hints
   moved from the raw panel onto the scroll area (`bab289c`).
2. Right panel restructured: Files+Queue+Progress (`top_widget`) | Activity Log
   (`log_group`) in vertical QSplitter (`self.log_splitter`),
   `setMaximumHeight(100)` removed, `setMinimumHeight(60)`, default sizes
   [420, 200], `setChildrenCollapsible(False)`, stretch only to the top
   sections; in-app WhatsThis help on the log group (`fc7e434`).

## Tests
- New: `tests/test_layout_dynamic.py` — 5 checks:
  1. left panel wrapped in QScrollArea
  2. Subtitles box keeps natural height (240/240 measured) at small window
  3. vertical 2-child log splitter exists
  4. `log_text` has no fixed height cap (`maximumHeight() > 1_000_000`)
  5. log grows past 150 px when splitter set to [400, 300] (177 px measured)
- TDD: both fixes verified RED first. Pre-fix proof (Task 1 review): with only
  `sub_group` exposed and no scroll area, the Subtitles box measured **60 px vs
  240 px sizeHint** on old code — a true behavioral regression test.
- Full suite: **215 checks green** across 10 files (baseline was 210):
  conversion_flags 23, e2e_format 6, encoder_engine 36, format_radio 14,
  layout_dynamic 5, self_update 16, thread_lifecycle 10, tools_startup_smoke 12,
  tool_updater 85, tool_worker 8.
- Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_layout_dynamic.py`

## Reversibility (each fix is an independent commit; commands verified by dry-run)
- Revert **both** fixes (single clean command — use this one):
  `git revert --no-edit fc7e434 bab289c`
  Order matters: reverting `bab289c` first or alone conflicts (modify/delete on
  the test file `bab289c` created). This combined command returns the suite to
  the 210-check baseline (the test file is deleted).
- Revert **only** the log splitter: `git revert --no-edit fc7e434` — applies
  cleanly; note it also reverts checks 3–5 of `tests/test_layout_dynamic.py`
  (those checks were ADDED by `fc7e434`), so the remaining 2 scroll checks
  still pass and the suite stays green (212 checks) — the log splitter is
  then simply untested.
- Revert **only** the scroll panel: `git revert --no-edit bab289c` — CONFLICTS
  on the test file; resolve with `git rm tests/test_layout_dynamic.py && git revert --continue`
  (the log-splitter fix remains, now without its tests).
- To also drop these docs: `git revert --no-edit HEAD` (docs only; independent
  of the two fix reverts).

## Layout probe evidence (Task 1/2 quality reviews)
- Left panel content ≈ 1128 px tall → the vertical scrollbar will be visible on
  essentially all screens (including the 1250×800 design default). This is
  expected, not a regression.
- Splitter drag limits: `top_widget.minimumSizeHint() = 480`,
  `log_group.minimumSizeHint() = 94`, `log_text` min 60 px at 760×520-class
  window — essential UI cannot be dragged away (`setChildrenCollapsible(False)`).
- Window growth goes to the top sections; log height changes only when dragged
  (`setStretchFactor` 1/0).

## Known pre-existing condition (out of scope, unchanged)
- Left panel horizontal clipping: content min width ≈ 397 px vs ≈ 260–300 px
  splitter allocation → ~100 px of right-edge content clipped at default split.
  This predates this change (old code clipped identically); the spec keeps
  horizontal sizing splitter-controlled (`ScrollBarAlwaysOff`). If noticeable
  during acceptance, follow-up: widen default left split 300 → ~420.

## Docs updated
`CHANGELOG.md` [Unreleased]; `docs/user_guide.md` §Logs; `docs/user_guide.ar.md`
§سجلات التشغيل; `AGENTS.md` (Responsive Window Sizing rules); in-app WhatsThis
on Activity Log (`ui/main_window.py`).
