# ADR-005: Alert rule representation and evaluation

- **Status:** Accepted
- **Date:** 2026-09-25

## Context
Users watch areas with threshold rules (FR-10) and every match must explain itself (FR-11, PRD P4).
Rules must never execute user code (ESD §11), alerts must not spam (PRD risk), and these are
application notifications, not official warnings.

## Decision
- **Rules are data**: a strictly validated `RuleConditions` object (pydantic, unknown fields
  rejected) combining with logical AND: minimum magnitude, depth bounds, area
  (`center` [lon, lat] + `radius_km`), PAGER alert levels, tsunami flag, event types (default
  `earthquake`). A rule needs at least one real condition; a rule matching everything is refused.
- **Deterministic, explainable evaluation** (`apps/alerts/matcher.py`, pure): each condition yields
  a clause such as `magnitude 5.9 >= 5.5`, `distance 214 km <= 300 km`. Numbers are printed with
  the fewest decimals that keep value and threshold distinct, so an explanation never reads as a
  contradiction (`magnitude 5.45 < 5.5`, not `5.5 < 5.5`). Missing source values never satisfy a
  condition. Distances use the same spherical model as ArangoDB's `GEO_DISTANCE`.
- **Evaluation inside the ingestion transaction** via the `AlertRuleObserver` (configured in
  `QUAKEWATCH_EVENT_OBSERVERS`), so an event and its matches commit together.
- **When a rule may fire:**
  - only for live-feed ingestion; backfills and dead-letter retries never notify;
  - only for events that occurred within 24 h of being observed;
  - only for events that occurred after the rule was created (1 h grace);
  - once per (rule, event): the match key is deterministic, so replays and later revisions never
    duplicate it, while a revision that *newly* satisfies a rule (e.g. magnitude upgrade) creates
    the match then (`trigger: revised`, with the changed fields).
- **Cooldown**: a match within `cooldown_minutes` of the rule's last notified match is recorded but
  flagged `notify: false, suppressed_reason: cooldown`.
- **Graph**: `users → user_owns_rule → alert_rules → rule_matched_event → events`; matches are also
  documents with the explanation, event snapshot and rule snapshot, so history survives rule
  deletion.
- **Ownership** is enforced in every repository query (`user_id` filter); other users' rules return
  404 (no existence leak). 25 rules per user.

## Consequences
- In-app notifications (feed + unread count) in the MVP; email/webhook adapters (V1.1) can consume
  `notify: true` matches without changing evaluation.
- A dry-run preview evaluates a rule against the last 7 days of stored events, with explanations,
  and no side effects.
