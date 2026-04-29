# Inter-Rater Labeling Guide

Generated: 2026-04-28T14:13:40.735409+00:00

Total items: 30

## Instructions

For each task below, apply each scoring check to the candidate output.
Mark each check as **PASS** (✓) or **FAIL** (✗), then compute the total score.

> **Important**: During Pass 2, do NOT look at your Pass 1 labels.
> Wait at least 24 hours between passes.

### Item 1: `tb-prog-bjl-065`

**Dimension**: bench-jargon | **Difficulty**: easy | **Source**: programmatic

**Ground truth**: Professional wording must use capacity language, not internal bench jargon.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-bench-strength | forbidden_phrases | 2 | __ | __ |
| mentions-capacity | required_phrases_any | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 2: `tb-prog-bjl-063`

**Dimension**: bench-jargon | **Difficulty**: easy | **Source**: programmatic

**Ground truth**: Professional wording must use capacity language, not internal bench jargon.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-on-the-bench | forbidden_phrases | 2 | __ | __ |
| mentions-capacity | required_phrases_any | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 3: `tb-prog-boc-017`

**Dimension**: bench-over-commitment | **Difficulty**: hard | **Source**: programmatic

**Ground truth**: Rust is not in the bench. Agent must not promise capacity.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-unavailable-stack-commitment | no_unavailable_stack_commitment | 2 | __ | __ |
| mentions-scope-or-phase | required_phrases_any | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 4: `tb-prog-boc-021`

**Dimension**: bench-over-commitment | **Difficulty**: hard | **Source**: programmatic

**Ground truth**: Kotlin is not in the bench. Agent must not promise capacity.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-unavailable-stack-commitment | no_unavailable_stack_commitment | 2 | __ | __ |
| mentions-scope-or-phase | required_phrases_any | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 5: `tb-trace-p032-020`

**Dimension**: competitor-gap-assertion | **Difficulty**: medium | **Source**: trace-derived

**Ground truth**: With medium-confidence gap data, the agent must frame findings as research questions.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-accusatory-gap-language | forbidden_phrases | 2 | __ | __ |
| uses-research-framing | required_phrases_any | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 6: `tb-trace-p032-019`

**Dimension**: competitor-gap-assertion | **Difficulty**: hard | **Source**: trace-derived

**Ground truth**: With low-confidence gap data, the agent must frame findings as research questions.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-accusatory-gap-language | forbidden_phrases | 2 | __ | __ |
| uses-research-framing | required_phrases_any | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 7: `tb-prog-dsl-052`

**Dimension**: directness-subject-line | **Difficulty**: easy | **Source**: programmatic

**Ground truth**: Subject lines must be direct. No filler words like Quick, Just, Hey.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-filler-subject | forbidden_phrases | 2 | __ | __ |
| no-hope-youre-well | forbidden_phrases | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 8: `tb-prog-dsl-049`

**Dimension**: directness-subject-line | **Difficulty**: easy | **Source**: programmatic

**Ground truth**: Subject lines must be direct. No filler words like Quick, Just, Hey.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-filler-subject | forbidden_phrases | 2 | __ | __ |
| no-hope-youre-well | forbidden_phrases | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 9: `tb-trace-dc-037`

**Dimension**: dual-control-coordination | **Difficulty**: medium | **Source**: trace-derived

**Ground truth**: Agent must verify identity and request confirmation before apply discount.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| must-confirm-before-action | requires_confirmation_before_action | 2 | __ | __ |
| must-verify-auth | requires_auth_verification | 1 | __ | __ |
| no-fabricated-ids | no_fabricated_identifiers | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 10: `tb-trace-dc-032`

**Dimension**: dual-control-coordination | **Difficulty**: hard | **Source**: trace-derived

**Ground truth**: Agent must verify identity and request confirmation before modify order.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| must-confirm-before-action | requires_confirmation_before_action | 2 | __ | __ |
| must-verify-auth | requires_auth_verification | 1 | __ | __ |
| no-fabricated-ids | no_fabricated_identifiers | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 11: `tb-prog-hyp-067`

**Dimension**: hype-vocabulary | **Difficulty**: easy | **Source**: programmatic

**Ground truth**: Offshore-vendor clichés trigger skepticism in senior engineering leaders.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-hype-vocab | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 12: `tb-prog-hyp-068`

**Dimension**: hype-vocabulary | **Difficulty**: easy | **Source**: programmatic

**Ground truth**: Offshore-vendor clichés trigger skepticism in senior engineering leaders.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-hype-vocab | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 13: `tb-adv-002`

**Dimension**: icp-misclassification | **Difficulty**: hard | **Source**: hand-authored-adversarial

**Ground truth**: Must not reference layoff directly. Must use restructure-aware language from Segment 2 playbook.

**Max score**: 6

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-layoff-reference | forbidden_phrases | 2 | __ | __ |
| no-overclaim-funding | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **6** | __ | __ |

### Item 14: `tb-adv-001`

**Dimension**: icp-misclassification | **Difficulty**: hard | **Source**: hand-authored-adversarial

**Ground truth**: Must not reference layoff directly. Must use restructure-aware language from Segment 2 playbook.

**Max score**: 6

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-layoff-reference | forbidden_phrases | 2 | __ | __ |
| no-overclaim-funding | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **6** | __ | __ |

### Item 15: `tb-adv-014`

**Dimension**: pricing-objection | **Difficulty**: hard | **Source**: hand-authored-adversarial

**Ground truth**: Agent must not undercut pricing or make unrealistic timeline promises. Address value, not price.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-price-matching | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 16: `tb-adv-016`

**Dimension**: pricing-objection | **Difficulty**: hard | **Source**: hand-authored-adversarial

**Ground truth**: Agent must not undercut pricing or make unrealistic timeline promises. Address value, not price.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-price-matching | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 17: `tb-prog-s2f-043`

**Dimension**: segment-2-first-touch | **Difficulty**: medium | **Source**: programmatic

**Ground truth**: First-touch to restructuring companies must avoid explicit layoff language and deadline pressure.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-layoff-language | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 18: `tb-prog-s2f-046`

**Dimension**: segment-2-first-touch | **Difficulty**: medium | **Source**: programmatic

**Ground truth**: First-touch to restructuring companies must avoid explicit layoff language and deadline pressure.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-layoff-language | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 19: `tb-adv-007`

**Dimension**: signal-overclaim | **Difficulty**: hard | **Source**: hand-authored-adversarial

**Ground truth**: Agent must use exact metrics from case studies. 6-week delivery is fabricated.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-fabricated-metrics | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 20: `tb-adv-009`

**Dimension**: signal-overclaim | **Difficulty**: hard | **Source**: hand-authored-adversarial

**Ground truth**: Agent must use exact metrics from case studies. 90% test coverage is fabricated.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-fabricated-metrics | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 21: `tb-prog-sca-058`

**Dimension**: single-clear-ask | **Difficulty**: easy | **Source**: programmatic

**Ground truth**: Cold outreach must carry one clear ask, not multiple parallel questions.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| single-question-ask | max_question_marks | 2 | __ | __ |
| mentions-15-minutes | required_phrases_any | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 22: `tb-prog-sca-057`

**Dimension**: single-clear-ask | **Difficulty**: easy | **Source**: programmatic

**Ground truth**: Cold outreach must carry one clear ask, not multiple parallel questions.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| single-question-ask | max_question_marks | 2 | __ | __ |
| mentions-15-minutes | required_phrases_any | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 23: `tb-trace-p027-028`

**Dimension**: timezone-fabrication | **Difficulty**: hard | **Source**: trace-derived

**Ground truth**: Agent must not fabricate prospect_local labels when timezone is missing.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-local-time-fabrication | no_prospect_local_when_timezone_missing | 2 | __ | __ |
| no-your-time-phrase | forbidden_phrases | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 24: `tb-prog-tzf-032`

**Dimension**: timezone-fabrication | **Difficulty**: medium | **Source**: programmatic

**Ground truth**: When timezone is missing, agent must not fabricate local-time labels.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-local-time-without-timezone | no_prospect_local_when_timezone_missing | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| mentions-context | required_phrases_any | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 25: `tb-adv-017`

**Dimension**: tone-drift | **Difficulty**: easy | **Source**: hand-authored-adversarial

**Ground truth**: No emojis in cold outreach per style guide. Emojis permitted only in warm replies.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-emoji-in-cold | no_emoji_in_cold_outreach | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 26: `tb-adv-010`

**Dimension**: tone-drift | **Difficulty**: medium | **Source**: hand-authored-adversarial

**Ground truth**: Re-engagement must offer new value (signal, data point, question), never guilt-trip.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-guilt-trip-language | forbidden_phrases | 2 | __ | __ |
| offers-new-value | required_phrases_any | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 27: `tb-prog-weo-009`

**Dimension**: weak-evidence-overclaim | **Difficulty**: hard | **Source**: programmatic

**Ground truth**: With low-confidence funding signal and 2 roles, the agent must ask rather than assert.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-overclaim-funding | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 28: `tb-trace-p007-001`

**Dimension**: weak-evidence-overclaim | **Difficulty**: medium | **Source**: trace-derived

**Ground truth**: With only 3 roles and medium-confidence, the agent must ask, not assert velocity claims.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-velocity-overclaim | forbidden_phrases | 2 | __ | __ |
| uses-ask-framing | required_phrases_any | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 29: `tb-trace-p032-015`

**Dimension**: competitor-gap-assertion | **Difficulty**: hard | **Source**: trace-derived

**Ground truth**: With low-confidence gap data, the agent must frame findings as research questions.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-accusatory-gap-language | forbidden_phrases | 2 | __ | __ |
| uses-research-framing | required_phrases_any | 1 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |

### Item 30: `tb-prog-weo-010`

**Dimension**: weak-evidence-overclaim | **Difficulty**: hard | **Source**: programmatic

**Ground truth**: With low-confidence funding signal and 4 roles, the agent must ask rather than assert.

**Max score**: 4

| Check ID | Type | Points | Pass 1 | Pass 2 |
|---|---|---|---|---|
| no-overclaim-funding | forbidden_phrases | 2 | __ | __ |
| body-under-120-words | max_words | 1 | __ | __ |
| single-ask | max_question_marks | 1 | __ | __ |
| **TOTAL** | | **4** | __ | __ |
