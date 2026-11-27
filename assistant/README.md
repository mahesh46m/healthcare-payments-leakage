# Ask the data: a small Medicare analytics assistant

A question-answering layer over the real CMS data in this repo. You ask a
question in plain English; the assistant answers through a small set of
allowlisted, read-only query functions, and every answer comes back with the
metric definitions and caveats attached.

## Safety model (the point of the exercise)

- There is no free-text SQL path. The only way to touch the data is through
  the functions in `query_functions.py`. Each one is a fixed read-only SELECT
  template with a few validated parameters (`limit` clamped to 1-50, specialty
  matched against actual values, `order` from a two-value whitelist).
- The database is opened with `read_only=True`.
- Two answering modes, same allowlist:
  - **Deterministic (default, no API key):** a keyword router (`router.py`)
    picks the function and parameters. Fully offline and reproducible.
  - **LLM (when `OPENAI_API_KEY` is set):** the model answers only by calling
    the allowlisted functions through tool calling (`TOOL_SCHEMAS`). It never
    sees or writes SQL, and the UI shows exactly which function produced each
    number. The allowlist is also enforced server-side in `app.py`.
- Out-of-scope questions get a plain refusal, not a guess.

## Files

| File | Role |
|---|---|
| `build_db.py` | Materialize `data/raw/*.csv` into `assistant/medicare.duckdb` with a snapshot stamp |
| `query_functions.py` | The allowlisted read-only functions, metric definitions, caveats, LLM tool schemas |
| `router.py` | Deterministic question-to-function router (offline mode) |
| `app.py` | Streamlit page |
| `test_questions.json` | 20-question test set with expected routing |
| `run_eval.py` | Runs the test set, executes each routed function, writes `eval_results.json` |
| `eval_results.json` | Measured results of the last eval run |
| `AI_USAGE.md` | How AI was used to build this, honestly |

## Run it

```bash
python src/download.py            # fetch the real public data (resumable)
python assistant/build_db.py      # build assistant/medicare.duckdb
```

For a quick start (and for the hosted demo), the app restores
`medicare.duckdb` automatically on first run when it is missing: from a local
`assistant/medicare.duckdb.gz` if present, otherwise by downloading the public
snapshot attached to this repo's
[`data-snapshot-2026-11` release](https://github.com/mahesh46m/healthcare-payments-analysis/releases/tag/data-snapshot-2026-11).
That snapshot is a gzip-compressed build of the same public data; no CMS
download is needed to try the app. The raw CSVs are still not committed;
`build_db.py` remains the way to rebuild from source.

```bash
streamlit run assistant/app.py    # open the page
```

`pip install -r assistant/requirements.txt` first if you need the extra
dependencies (streamlit; `openai` only for LLM mode).

## Measured evaluation

`run_eval.py` routes all 20 test questions, then executes each routed
function against the real database. Latest measured result
(`eval_results.json`, snapshot built 2026-11-27 UTC):

- **20/20 questions routed to the expected function (100%), with the expected
  parameters where the test specifies them.**
- Every routed function executed successfully against the real data and
  returned rows.

Read that number carefully: the 20 questions were written alongside the
router, so this is **in-sample** coverage of the intended question set, not a
claim of accuracy on arbitrary phrasings. The eval exists so that claim stays
honest and re-runnable: change the router, re-run, and the number moves.

## Data snapshot caveat

The assistant's database is built from whatever `src/download.py` pulls, and
CMS refreshes these datasets. The snapshot built 2026-11-27 UTC contains
228,520 Maryland service rows (vs 174,983 in the static analysis), so the
assistant's totals (e.g. $10.39B submitted) differ from the numbers in
`docs/findings.md` and the charts, which reflect the earlier pull. The app
header always shows the snapshot timestamp and row counts so the two are never
confused.

## NPIs in results

Some functions return NPIs. These come from the public CMS files; like the
rest of this project, lists are generated locally from public data and the
repo commits no provider-level NPI extracts.
