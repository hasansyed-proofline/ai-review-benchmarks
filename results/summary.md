# Benchmark Summary (`feat/benchmark-harness`)

## Scope & Execution
- **Providers & Repos:** Proofline (`hasansyed-proofline/bench-proofline`) and CodeRabbit (`hasansyed-proofline/bench-coderabbit`), each bootstrapped from `upstream/pilot/base` with one reviewer app per repo.
- **Conditions & Runs:** 22 attempts total (`r1`):
  - `code-only`: Cases `01`–`08` for both Proofline and CodeRabbit (16 runs).
  - `with-snapshot`: Cases `04`–`06` with `cases/XX/evidence.md` appended under `## Deployment snapshot` for both providers (6 runs).
- **Artifacts:** Raw payloads in `results/raw/` and run metadata in `results/state.json`.
- **Harness Fixes:** Filtered bot feedback by target bot login (`f7568fc`) and filtered check runs by `started_at >= opened_at` when commit SHAs were shared across runs (`653ffbf`).

## Rubric Alignment (`benchmark/rubric.json` & `benchmark/protocol.md`)

### Deployment-Dependent Cases (`04`–`06`: `code-only` calibration vs. `with-snapshot` evidence grounding)
- **Case 04 (`Retire the legacy delivery column`):**
  - *Proofline:* Focused on SQLite migration/versioning concurrency (`console.py` / `user_version`) in both `code-only` and `with-snapshot` rather than citing the `elm` `workers-17` (`SELECT id, legacy_format ...`, `inventory-204`) vs. `cedar` snapshot.
  - *CodeRabbit:* Flagged a SQLite `DROP COLUMN` version floor (`3.35.5+` vs. `README.md`) in `code-only`; in `with-snapshot`, identified `elm` having 2 `workers-17` replicas still polling `legacy_format` and recommended retiring them before dropping the column.
- **Case 05 (`Increase export batch size`):**
  - *Proofline:* Quiet (`0` inline/review findings) in both `code-only` and `with-snapshot`.
  - *CodeRabbit:* No inline finding in `code-only`; in `with-snapshot`, identified `cedar` (`max_rows_per_request: 40` with `70` ready rows, `archive-318`) rejecting 50-row archive requests while `elm` (`100`) allows them.
- **Case 06 (`Use the new delivery queue`):**
  - *Proofline:* Flagged `README.md` quickstart still using `--queue reports` in both `code-only` and `with-snapshot` without citing the `elm` vs. `cedar` queue subscription snapshot (`subscriptions-416`).
  - *CodeRabbit:* Flagged `README.md` worker queue targeting in `code-only`; in `with-snapshot`, identified `elm` only subscribing to `reports` (stranding 8 due jobs in the window) while `cedar` subscribes to both `reports` and `report-dispatch`.

### Code-Only Bugs (`01`–`03`) & Clean Controls (`07`–`08`)
- Raw responses for `01` (cursor pagination), `02` (CSV escaping), `03` (batch remainder on non-multiples of 20), and `07`–`08` (partial index and summary `total` field) are stored in `results/raw/` for detailed grading (`caught`, `clean_pass`, `missed`, `false_positive`, `valid_extra`).
