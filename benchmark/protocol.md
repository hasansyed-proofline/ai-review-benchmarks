# Benchmark Protocol

Frozen before running any AI reviewer.

## Unit of observation
One attempt is keyed by `(provider, case_id, condition, run_id)`.
Each recorded attempt saves `repo`, `pr_number`, `pr_url`, `base_sha`, `head_sha`, `trigger`, `notes`, timestamps, `status`, and the raw GitHub review/comment payloads.
Webhook retries stay in the same attempt. Intentional reruns open a new PR with a new `run_id` and are reported separately as repeats.

## Isolation rules
- One private repo per provider under `hasansyed-proofline` (e.g., `bench-proofline`, `bench-coderabbit`).
- Every provider repo is initialized strictly from `upstream/pilot/base` (app source + usage guide only—no `cases/`, rubric, or harness files).
- Only one reviewer GitHub App is installed per provider repo ("Only select repositories").
- Cross-repo learning/indexing is turned off where configurable; any uncertainty is noted in `providers.json`.

## Context conditions
- `code-only` (Cases 01–08): PR title and body verbatim from `cases/XX/title.txt` and `cases/XX/body.md`.
- `with-snapshot` (Cases 04–06): Separate PR on the same case commit (`head_sha`) with `cases/XX/evidence.md` appended under `## Deployment snapshot`, avoiding cross-condition PR comment history.

## Scoring rubric
Graded against `benchmark/rubric.json` with provider names hidden:
- `caught` (Cases 01–03): Identifies the concrete bug and why it fails.
- `calibrated` (Cases 04–06, `code-only`): Flags that safety depends on live deployment state without guessing.
- `caught_with_evidence` (Cases 04–06, `with-snapshot`): Names the affected site (`elm` or `cedar`) and cites the snapshot evidence.
- `clean_pass` (Cases 07–08): Successful check/review completion with no false-positive bug/crash warnings (failed check runs are recorded as `failed`, not `clean_pass`).
- `missed` / `false_positive` / `duplicate` / `valid_extra` logged separately with raw comment references.
