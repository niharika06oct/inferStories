# Entity registry — pre-merge manual checks

Run after `alembic upgrade head` and with API + web up.

## 1. Jon / Jon Snow / I (POV = Jon Snow)

1. New story → chapter with **POV** = `Jon Snow`.
2. Text (example):

   ```
   I distrusts Stefan. Jon distrusts the Wildlings. Jon Snow looked north.
   ```

3. **Save & analyze memory**.
4. **GET** `/stories/{id}/entities` (or open story memory in UI when wired):
   - Exactly **one** entity with `canonical_name` = `Jon Snow`.
   - Aliases include `I`, `me`, `myself` (from POV registration).
   - After extraction, alias `Jon` appears (shorter surface form merged in).
5. Claims panel: subjects show `Jon Snow` / `Jon` for narrator lines; all use the **same** `subject_entity_id`.

## 2. Re-analyze — no duplicate entities

1. Same story, note entity count (e.g. Jon Snow, Stefan, Wildlings).
2. Approve one or two claims.
3. Add a sentence; **Save & analyze** again.
4. Entity count **unchanged**; still one `Jon Snow` row, not separate `Jon` + `Jon Snow` entities.

## 3. Semantic predicates (not `claim_type`)

After analyze, claim rows should show predicates like:

| Text hint | Expected `predicate` | `claim_type` stays |
|-----------|----------------------|--------------------|
| trusts | `trusts` | `relationship_state` |
| distrusts | `distrusts` | `relationship_state` |
| is the half-brother of | `is_half_brother_of` | `relationship_state` |

**Not** `relationship_state` or other category slugs in the `predicate` column.

Automated: `pytest tests/test_merge_verification.py`
