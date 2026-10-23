# Holdout V2 routing analysis

Holdout V2 is sealed historical evidence. Its prompts, fixtures and official result
must not be modified or rerun as a blind benchmark. The locked run recorded 24
routing-insufficient cases among 72; Qwen succeeded on 45 of the 48 cases whose
menus were sufficient. One post-run fixture/oracle issue is documented separately
in the existing post-run audit and does not change the official score.

The following classification uses only structural categories. Case IDs identify
the historical failures; this document intentionally omits their exact sentences.

| Case | Primary structural cause | Secondary cause |
| --- | --- | --- |
| HV2-004 | DOMAIN_LOSS | Diagnostic menu lacked a process contributor |
| HV2-007 | UNKNOWN_SYMPTOM_EXPRESSION | PROTOTYPE_GATE_FAILURE |
| HV2-008 | UNKNOWN_SYMPTOM_EXPRESSION | NO_TOOL_FALSE_NEGATIVE |
| HV2-011 | DOMAIN_LOSS | Power-plan evidence was absent |
| HV2-012 | UNKNOWN_SYMPTOM_EXPRESSION | NO_TOOL_FALSE_NEGATIVE |
| HV2-013 | UNKNOWN_SYMPTOM_EXPRESSION | NO_TOOL_FALSE_NEGATIVE |
| HV2-014 | UNKNOWN_SYMPTOM_EXPRESSION | NO_TOOL_FALSE_NEGATIVE |
| HV2-018 | UNKNOWN_SYMPTOM_EXPRESSION | NO_TOOL_FALSE_NEGATIVE |
| HV2-019 | DOMAIN_LOSS | GPU contributor absent from memory-pressure menu |
| HV2-020 | AMBIGUOUS_LANGUAGE | Irrelevant task tool won |
| HV2-026 | UNKNOWN_ENTITY_EXPRESSION | NO_TOOL_FALSE_NEGATIVE |
| HV2-033 | MISSING_INTENT_PROTOTYPE | Availability question without calendar noun |
| HV2-038 | UNKNOWN_VERB | Calendar write resolver did not resolve the action |
| HV2-041 | UNKNOWN_VERB | PROTOTYPE_GATE_FAILURE |
| HV2-043 | UNKNOWN_VERB | PROTOTYPE_GATE_FAILURE |
| HV2-044 | UNKNOWN_VERB | Media control degraded to status |
| HV2-050 | DOMAIN_LOSS | Locator appeared without search capability |
| HV2-055 | MISSING_INTENT_PROTOTYPE | Model context phrasing lacked model noun |
| HV2-059 | CLAUSE_SPLIT_FAILURE | Calendar half disappeared |
| HV2-061 | CLAUSE_SPLIT_FAILURE | Disk half disappeared |
| HV2-062 | CLAUSE_SPLIT_FAILURE | Media half disappeared |
| HV2-063 | CLAUSE_SPLIT_FAILURE | File search half disappeared |
| HV2-064 | CLAUSE_SPLIT_FAILURE | Process-status half disappeared |
| HV2-066 | NO_TOOL_FALSE_NEGATIVE | Educational question exposed live tools |

The dominant themes are clause preservation and weak intent recall when the exact
manual concept vocabulary is absent. These classifications guide new development
examples and structural changes; they are not sentence-level rules.
