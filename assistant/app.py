"""Streamlit page: ask questions about the Medicare payment data.

Two answering modes, same safety model:

  * Deterministic (default): a keyword router maps the question to one of the
    allowlisted read-only query functions in query_functions.py.
  * LLM (when OPENAI_API_KEY is set): the model answers ONLY by calling those
    same allowlisted functions through tool calling. It never sees or writes
    SQL, never touches the database directly, and every data answer is shown
    with its metric definitions and caveats.

Run from the repo root, after assistant/build_db.py:
    streamlit run assistant/app.py
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import query_functions as qf
import router

st.set_page_config(page_title="Ask the Medicare data", page_icon=":bar_chart:", layout="wide")

SYSTEM_PROMPT = """You are an analytics assistant for a public Medicare payment dataset
(Maryland Part B 2024, national inpatient FY2024, OIG exclusion list).

Rules you must follow:
1. Answer data questions ONLY by calling the provided tools. Never invent numbers.
2. If a question needs something the tools cannot answer, say so plainly.
3. In your answer, always include the relevant caveats returned by the tool.
4. Use the metric definitions returned by the tools when you mention a metric.
5. Keep answers short: what was found, the number, the caveat."""


def answer_offline(question):
    specialties = qf.list_specialties()
    fn, params_or_reason = router.route(question, specialties=specialties)
    if fn is None:
        return {"function": None, "summary": f"I can't answer that from this dataset ({params_or_reason}).",
                "rows": [], "definitions": {}, "caveats": []}
    return qf.FUNCTIONS[fn](**(params_or_reason or {}))


def answer_with_llm(question):
    from openai import OpenAI

    client = OpenAI()
    tools = [{"type": "function", "function": s} for s in qf.TOOL_SCHEMAS]
    msgs = [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question}]
    calls = []
    for _ in range(4):  # bounded tool-call loop
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=msgs, tools=tools, tool_choice="auto")
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return {"narrative": msg.content, "calls": calls}
        msgs.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            if name not in qf.FUNCTIONS:  # allowlist enforcement, belt and braces
                result = {"error": f"function {name!r} is not allowlisted"}
            else:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    result = qf.FUNCTIONS[name](**args)
                except Exception as e:  # surface a safe error, never a stack trace to the model loop
                    result = {"error": f"{type(e).__name__}: {e}"}
            calls.append({"name": name, "result": result})
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)})
    return {"narrative": "Stopped after 4 tool-call rounds without a final answer.", "calls": calls}


def render_result(res):
    if res.get("narrative"):
        st.markdown(res["narrative"])
    elif res.get("summary"):
        st.markdown(res["summary"])
    if res.get("rows"):
        st.dataframe(pd.DataFrame(res["rows"]))
    for call in res.get("calls", []):
        r = call["result"]
        with st.expander(f"data: {call['name']}"):
            if r.get("summary"):
                st.write(r["summary"])
            if r.get("rows"):
                st.dataframe(pd.DataFrame(r["rows"]))
            for c in r.get("caveats", []):
                st.info(c)
    if res.get("definitions"):
        with st.expander("metric definitions"):
            for k, v in res["definitions"].items():
                st.markdown(f"**{k}** - {v}")
    for c in res.get("caveats", []):
        st.info(c)


def main():
    st.title("Ask the Medicare data")
    try:
        snap = qf.snapshot()
        st.caption(
            "Real public data: CMS Medicare Part B 2024 (Maryland), CMS inpatient FY2024 (national), "
            f"HHS-OIG exclusion list. Database snapshot built {snap['built_at']} UTC - "
            + ", ".join(f"{k}: {v:,} rows" for k, v in snap["counts"].items()))
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    use_llm = bool(os.environ.get("OPENAI_API_KEY"))
    st.sidebar.markdown("### How answers are produced")
    if use_llm:
        st.sidebar.write("LLM mode: the model answers only by calling allowlisted read-only "
                         "query functions. It never writes SQL.")
    else:
        st.sidebar.write("Deterministic mode (no API key set): a keyword router picks one of the "
                         "allowlisted read-only query functions.")
    st.sidebar.write("Every data answer comes with its metric definitions and caveats.")

    examples = [
        "How much did Medicare pay Maryland providers in 2024 overall?",
        "Which specialties have the biggest gap between charges and payments?",
        "Which providers are paid far above their specialty peers?",
        "Are any paid providers on the OIG exclusion list?",
        "Which hospitals have the lowest payment-to-charge ratio?",
    ]
    q = st.text_input("Ask a question about the data",
                      placeholder="e.g. Which procedure codes have the largest charge-to-payment gap?")
    st.caption("Examples: " + " | ".join(examples))
    if not q:
        st.stop()
    with st.spinner("answering through the allowlisted query functions..."):
        res = answer_with_llm(q) if use_llm else answer_offline(q)
    if res.get("function"):
        st.caption(f"answered by: `{res['function']}` (allowlisted, read-only)")
    render_result(res)


if __name__ == "__main__":
    main()
