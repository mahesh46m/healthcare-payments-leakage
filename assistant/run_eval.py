"""Run the 20-question test set against the deterministic router and measure results.

For each question: route it, compare against the expected function (and params
where specified), then execute the routed function to prove the answer path
works end to end. Writes measured results to assistant/eval_results.json.

These are IN-SAMPLE routing results: the questions were written alongside the
router. Treat the number as "the assistant answers the questions it was built
for", not as general accuracy on arbitrary phrasings.

Run from the repo root, after assistant/build_db.py:
    python assistant/run_eval.py
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import query_functions as qf
import router


def main():
    tests = json.loads((HERE / "test_questions.json").read_text())
    specialties = qf.list_specialties()
    results = []
    correct = 0
    for t in tests:
        q = t["q"]
        fn, params_or_reason = router.route(q, specialties=specialties)
        expect_fn = t["expect_fn"]
        ok_fn = (fn == expect_fn)
        ok_params = True
        if ok_fn and fn and "expect_params" in t:
            for k, v in t["expect_params"].items():
                if params_or_reason.get(k) != v:
                    ok_params = False
        ok = ok_fn and ok_params
        correct += int(ok)
        entry = {"q": q, "expected_fn": expect_fn, "routed_fn": fn, "correct": ok}
        if fn:
            t0 = time.time()
            out = qf.FUNCTIONS[fn](**(params_or_reason or {}))
            entry["exec_ms"] = round(1000 * (time.time() - t0), 1)
            entry["rows_returned"] = len(out["rows"])
            entry["summary"] = out["summary"]
        else:
            entry["reason"] = params_or_reason
        results.append(entry)
    snap = qf.snapshot()
    report = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_snapshot": snap,
        "router": "deterministic keyword router (no LLM in the loop for this eval)",
        "scope_note": ("In-sample: the 20 questions were written alongside the router. "
                       "This measures coverage of the intended question set, not accuracy "
                       "on arbitrary user phrasings."),
        "questions": len(tests),
        "correct": correct,
        "routing_accuracy": round(correct / len(tests), 3),
        "results": results,
    }
    (HERE / "eval_results.json").write_text(json.dumps(report, indent=1, default=str))
    print(f"{correct}/{len(tests)} correct "
          f"({report['routing_accuracy'] * 100:.0f}% routing accuracy, in-sample)")
    for r in results:
        if not r["correct"]:
            print(f"  MISS: {r['q']!r} expected {r['expected_fn']}, got {r['routed_fn']}")
    print(f"wrote {HERE / 'eval_results.json'}")


if __name__ == "__main__":
    main()
