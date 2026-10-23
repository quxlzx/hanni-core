# Campaign 8 independent visual rubric

This rubric is fixed before production design changes. Visual development review
can iterate, while private functional inputs and answers remain untouched until
the final source freeze. Scores require actual owned Windows HANNI app pixels;
prior browser screenshots do not establish native desktop quality.

Each primary screen and Mini receives an independent score across these dimensions:

| Dimension | Weight | Evidence required |
| --- | ---: | --- |
| Typography and readability | 20% | Native pixels, actual loaded font, size/weight/line-height; dense labels, tables, long text and controls |
| Hierarchy and task clarity | 20% | Primary action, navigation, meaningful grouping and readable state priority |
| Spacing and alignment | 15% | Consistent baselines, column relationships, intentional whitespace and reachable scroll areas |
| Density and adaptation | 15% | At least two physical window sizes; no inaccessible clipping, overlapping chrome or unintended root horizontal scrolling |
| Truthful states and feedback | 15% | Current original backend API evidence for availability, permissions, empty/error/stale/working states |
| Windows interaction quality | 10% | Owned HWND identity, focus and keyboard controls, resize/minimize/restore and native title-bar behavior |
| Finishing detail | 5% | Contrast, borders, transitions and control consistency without distracting decoration |

Scores use 0–10: 0–2 unusable or misleading; 3–4 major defects; 5–6 serviceable
with visible limitations; 7–8 good but with material rough edges; 8.6–9.4 polished
and evidenced; 9.5–10 exceptional, requiring specific supporting evidence. The
weighted screen and typography scores must each be at least 8.6 and the arithmetic mean across all
reviewed primary screens must exceed 8.5. A blocker is reported honestly rather
than raising a score to meet the target. A critical false claim about owner
state prevents acceptance even if the screenshot looks polished. Unmeasured
dimensions stay unmeasured; an incomplete score cannot qualify for acceptance.

AI-template appearance is rated separately from 0–10 and must be no more than 2.
The rating cites visible evidence: repeated identical feature-card rows, gradients
or glowing/frosted decoration, badge/slogan clutter, invented social proof,
decorative icon tiles, repetitive numerical labels, generic heading language,
and gratuitous nesting. Member emojis requested by the owner are intentional
cluster labels, not an automatic template penalty. A technical card/table is not
penalized merely for using a border. Typography improvement is judged from pixels,
not from a fashionable font name.

If typography scores below its threshold, compare the current base font against
at least five available local alternatives using the same actual text, sizes,
weights, columns and Windows app capture method. Candidate identities, fallback
and font availability must be recorded; absent fonts are not comparisons. Do not
download fonts or claim the proprietary OpenAI face is installed. Report whether
the comparison changes the result and which defects are layout rather than font.

Capture records include PID and creation time, HWND/class, executable/source/asset
hashes, exact capture method, window and client rectangles, Windows DPI and CDP
device metrics. OS DPI is observed, never changed. CDP emulation is labelled
separately and cannot be presented as a test at another actual Windows DPI level.
Native HWND capture is restricted to owned app surfaces; a CDP client screenshot
fallback is disclosed and cannot substitute for native capture acceptance.
Screenshots remain ignored/private, with hashes and review findings published.

Development screenshots may reveal and guide repairs. Every cycle records its
source identity, scores, concrete defects and actual checks. Final acceptance
uses frozen source, fresh native evidence and the consumed private functional
holdout; it does not tune or retry private failures. Visual grades are human-like
independent judgments with stated evidence and limits, not model agreement or an
automatically fitted metric.
