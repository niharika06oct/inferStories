# Deferred Bug Backlog

This document tracks known bugs we are **not fixing right now**, but want to fix eventually. Use it to keep focus on current product work without losing important issues.

## 1. Claim / Continuity Click Text Focus Is Still Unreliable

**Status:** Deferred  
**Area:** Web editor, claim evidence highlighting, continuity navigation  
**Priority:** High later, but not blocking current work

When clicking a claim or continuity issue, the app should open the relevant chapter, scroll to the referenced passage, and highlight the exact affected text. This still does not happen correctly in all cases.

Known symptoms:

- Clicking a claim or continuity issue may open the correct chapter but fail to scroll to the exact referenced text.
- Highlighting can be missing, partial, or attached to the wrong nearby phrase.
- This affects both normal claim focus and continuity issue focus.

Likely areas to revisit:

- `apps/web/lib/claimEvidenceSpan.ts`
- `apps/web/components/SceneTextEditor.tsx`
- `apps/web/app/StoryEditor.tsx`
- `apps/api/app/validation_evidence.py`

Notes for later:

- Re-check whether stored `anchor_text`, `anchor_length`, and `text_offset` are reliable enough.
- Consider rendering highlight/scroll from a stable mark ref after React has painted the chapter text.
- Consider storing stronger evidence anchors at extraction time, such as normalized quote hashes or start/end offsets from extraction.
