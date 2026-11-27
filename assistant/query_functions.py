"""Allowlisted read-only query functions for the Medicare analytics assistant.

These are the ONLY ways the assistant (deterministic router or LLM) can touch
the data. There is no free-text SQL path: every function is a fixed, read-only
query template with a small set of validated parameters, and every answer comes
back with the metric definition and caveats attached.

Database access: opened with read_only=True; only SELECT statements below exist.
"""
import json
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent / "medicare.duckdb"

DEFINITIONS = {
    "submitted": "Submitted charges: what providers billed Medicare (Tot_Srvcs x Avg_Sbmtd_Chrg). "
                 "Charges are list prices, not what Medicare agreed to pay.",
    "allowed": "Medicare allowed amount: what Medicare determined was payable for the service.",
    "paid": "Medicare payment amount: what Medicare actually paid (before beneficiary cost sharing).",
    "paid_ratio": "paid / submitted. Low values are normal in Medicare (charges are list prices); "
                  "the useful comparisons are between peers, not against 100%.",
    "gap": "submitted - paid, in dollars. A large gap mostly reflects charge inflation; "
           "it is a starting point for questions, not evidence of a problem by itself.",
    "robust_z": "0.6745 x (pay_per_bene - specialty_median) / specialty_MAD. A robust z-score using "
                "the median and median absolute deviation, so a few extreme providers do not skew the baseline.",
    "excess_vs_peer_median": "Provider's total paid minus (their beneficiary count x specialty median paid per "
                             "beneficiary). Dollars above what a median peer would have been paid for the same panel size.",
    "bene_days_per_workday": "Beneficiary-days of one service divided by 250 working days. Values above ~40 mean "
                             "the provider would have to deliver that service to 40+ distinct patients every working day.",
    "paid_ratio_hospital": "Inpatient: Tot_Mdcr_Pymt_Amt / Tot_Submtd_Cvrd_Chrg for hospitals with 500+ discharges.",
}

CAVEATS = {
    "partb": "Part B Physician & Other Practitioners file, 2024, Maryland subset only. "
             "CMS suppresses cells with 10 or fewer beneficiaries, so detail rows undercount totals.",
    "review": "This is a review list, not an accusation. High values can have legitimate explanations "
              "(group billing under one NPI, specialized practice, data quirks).",
    "q4": "Service-level detail covers roughly 63% of provider-summary paid dollars (snapshot-dependent): "
          "CMS cell suppression and services not in the detail file explain most of the gap. Gaps are expected.",
    "q6": "An NPI on the exclusion list means 'needs review', not wrongdoing: 2024 payments may pre-date "
          "the exclusion, and name/NPI matches can be data errors. Check the exclusion date against service dates.",
    "inp": "Inpatient file is national FY2024 and hospital-level; the Part B files are Maryland 2024 and "
           "provider-level. Do not mix the two scopes in one comparison.",
}


def _con():
    if not DB.exists():
        raise FileNotFoundError("assistant/medicare.duckdb not found - run python assistant/build_db.py first")
    return duckdb.connect(str(DB), read_only=True)


def _limit(limit, default=10, hi=50):
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, hi))


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _out(fn, definition_keys, caveat_keys, rows, summary, extra=None):
    out = {
        "function": fn,
        "definitions": {k: DEFINITIONS[k] for k in definition_keys},
        "caveats": [CAVEATS[k] for k in caveat_keys],
        "summary": summary,
        "rows": rows,
    }
    if extra:
        out.update(extra)
    return out


def snapshot():
    con = _con()
    try:
        row = con.execute("SELECT built_at, counts_json FROM snapshot").fetchone()
    finally:
        con.close()
    return {"built_at": row[0], "counts": json.loads(row[1])}


def list_specialties():
    con = _con()
    try:
        return [r[0] for r in con.execute(
            "SELECT DISTINCT Rndrng_Prvdr_Type FROM svc ORDER BY 1").fetchall()]
    finally:
        con.close()


def metric_definitions():
    return _out("metric_definitions", list(DEFINITIONS), [],
                [], "Metric definitions used across this project.")


def dataset_totals():
    con = _con()
    try:
        s = con.execute("SELECT count(*), round(sum(sbmtd)), round(sum(allowed)), round(sum(paid)) FROM svc").fetchone()
        p = con.execute("SELECT count(distinct Rndrng_NPI), round(sum(Tot_Mdcr_Pymt_Amt)) FROM prov").fetchone()
        i = con.execute(
            "SELECT count(*), round(sum(Tot_Mdcr_Pymt_Amt)/sum(Tot_Submtd_Cvrd_Chrg), 3) FROM inp").fetchone()
    finally:
        con.close()
    rows = [{
        "md_service_rows": s[0], "submitted_charges": s[1], "allowed": s[2], "medicare_paid_detail": s[3],
        "md_providers": p[0], "medicare_paid_provider_summary": p[1],
        "inpatient_hospitals_national": i[0], "inpatient_paid_ratio_overall": i[1],
    }]
    paid_pct = round(100.0 * s[3] / s[1], 1) if s[1] else None
    summary = (f"Maryland 2024 Part B: ${s[1]:,} submitted vs ${s[3]:,} paid in the service-level file "
               f"({paid_pct}% paid) across {p[0]:,} providers. Provider-summary paid total is ${p[1]:,}; "
               f"the detail file covers only part of it (see reconciliation).")
    return _out("dataset_totals", ["submitted", "allowed", "paid"], ["partb", "q4"], rows, summary)


def paid_vs_submitted_by_specialty(specialty=None, limit=10):
    n = _limit(limit)
    con = _con()
    try:
        if specialty:
            match = con.execute(
                "SELECT DISTINCT Rndrng_Prvdr_Type FROM svc WHERE lower(Rndrng_Prvdr_Type) = lower(?)",
                [str(specialty)]).fetchone()
            if not match:
                return _out("paid_vs_submitted_by_specialty", ["submitted", "paid", "gap", "paid_ratio"],
                            ["partb"], [],
                            f"No specialty named '{specialty}' in the data. Call list_specialties to see valid values.")
            rows = _rows(con.execute(
                "SELECT Rndrng_Prvdr_Type AS specialty, round(sum(sbmtd)) AS submitted, round(sum(paid)) AS paid, "
                "round(sum(sbmtd)-sum(paid)) AS gap, round(sum(paid)/sum(sbmtd),3) AS paid_ratio "
                "FROM svc WHERE lower(Rndrng_Prvdr_Type) = lower(?) GROUP BY 1", [match[0]]))
            summary = f"{match[0]}: ${rows[0]['submitted']:,} submitted, ${rows[0]['paid']:,} paid."
        else:
            rows = _rows(con.execute(
                "SELECT Rndrng_Prvdr_Type AS specialty, round(sum(sbmtd)) AS submitted, round(sum(paid)) AS paid, "
                "round(sum(sbmtd)-sum(paid)) AS gap, round(sum(paid)/sum(sbmtd),3) AS paid_ratio "
                f"FROM svc GROUP BY 1 HAVING sum(sbmtd) > 5e6 ORDER BY gap DESC LIMIT {n}"))
            summary = f"Top {len(rows)} specialties by submitted-minus-paid gap (specialties over $5M submitted)."
    finally:
        con.close()
    return _out("paid_vs_submitted_by_specialty", ["submitted", "paid", "gap", "paid_ratio"],
                ["partb"], rows, summary)


def largest_gap_codes(limit=10):
    n = _limit(limit)
    con = _con()
    try:
        rows = _rows(con.execute(
            "SELECT HCPCS_Cd AS hcpcs, any_value(HCPCS_Desc) AS description, round(sum(sbmtd)) AS submitted, "
            "round(sum(paid)) AS paid, round(sum(sbmtd)-sum(paid)) AS gap, "
            "round(sum(paid)/sum(sbmtd),3) AS paid_ratio "
            f"FROM svc GROUP BY 1 ORDER BY gap DESC LIMIT {n}"))
    finally:
        con.close()
    return _out("largest_gap_codes", ["submitted", "paid", "gap", "paid_ratio"], ["partb"], rows,
                f"Top {len(rows)} procedure codes by submitted-minus-paid gap.")


def provider_outliers_vs_peers(limit=10):
    n = _limit(limit)
    con = _con()
    try:
        rows = _rows(con.execute(
            "WITH base AS (SELECT Rndrng_NPI npi, Rndrng_Prvdr_Type specialty, Rndrng_Prvdr_City city, "
            "Tot_Mdcr_Pymt_Amt pay, Tot_Benes benes, Tot_Mdcr_Pymt_Amt/NULLIF(Tot_Benes,0) AS pay_per_bene "
            "FROM prov WHERE Tot_Benes>=50 AND Rndrng_Prvdr_Ent_Cd='I'), "
            "stats AS (SELECT specialty, count(*) n, median(pay_per_bene) med FROM base GROUP BY 1), "
            "mad AS (SELECT b.specialty, median(abs(b.pay_per_bene-s.med)) AS mad, any_value(s.med) med, "
            "any_value(s.n) n FROM base b JOIN stats s USING(specialty) GROUP BY 1) "
            "SELECT b.npi, b.specialty, b.city, round(b.pay) AS total_paid, b.benes, "
            "round(b.pay_per_bene) AS pay_per_bene, round(m.med) AS peer_median, "
            "round(0.6745*(b.pay_per_bene-m.med)/NULLIF(m.mad,0),1) AS robust_z, "
            "round(b.pay-b.benes*m.med) AS excess_vs_peer_median "
            f"FROM base b JOIN mad m USING(specialty) WHERE m.n>=30 ORDER BY robust_z DESC LIMIT {n}"))
    finally:
        con.close()
    return _out("provider_outliers_vs_peers", ["robust_z", "excess_vs_peer_median"],
                ["partb", "review"], rows,
                f"Top {len(rows)} individual providers by robust z-score of payment per beneficiary "
                f"vs their specialty median (specialties with 30+ providers, providers with 50+ beneficiaries).")


def reconciliation_summary():
    con = _con()
    try:
        t = con.execute("SELECT round(sum(paid)) FROM svc").fetchone()[0]
        p = con.execute("SELECT round(sum(Tot_Mdcr_Pymt_Amt)) FROM prov").fetchone()[0]
        missing = con.execute(
            "SELECT count(*) FROM prov p LEFT JOIN (SELECT Rndrng_NPI, sum(paid) sp FROM svc GROUP BY 1) s "
            "ON p.Rndrng_NPI = s.Rndrng_NPI WHERE coalesce(s.sp, 0) = 0").fetchone()[0]
        top = _rows(con.execute(
            "WITH a AS (SELECT Rndrng_NPI npi, sum(paid) svc_paid FROM svc GROUP BY 1), "
            "b AS (SELECT Rndrng_NPI npi, Tot_Mdcr_Pymt_Amt prov_paid FROM prov) "
            "SELECT b.npi, round(b.prov_paid) prov_paid, round(coalesce(a.svc_paid,0)) svc_paid, "
            "round(b.prov_paid-coalesce(a.svc_paid,0)) AS unreconciled "
            "FROM b LEFT JOIN a USING(npi) ORDER BY abs(unreconciled) DESC LIMIT 5"))
    finally:
        con.close()
    cover = round(100.0 * t / p, 1) if p else None
    rows = [{"provider_summary_paid": p, "service_detail_paid": t,
             "detail_coverage_pct": cover, "providers_with_no_service_rows": missing}]
    summary = (f"Service-level detail shows ${t:,} of the ${p:,} in the provider summary "
               f"({cover}% coverage). {missing:,} providers have no service-level rows at all.")
    return _out("reconciliation_summary", ["paid"], ["partb", "q4"], rows, summary,
                extra={"largest_unreconciled_providers": top})


def high_volume_services(limit=10):
    n = _limit(limit)
    con = _con()
    try:
        rows = _rows(con.execute(
            "SELECT Rndrng_NPI npi, Rndrng_Prvdr_Type specialty, HCPCS_Cd, HCPCS_Desc, Tot_Srvcs, "
            "Tot_Bene_Day_Srvcs, round(Tot_Srvcs/NULLIF(Tot_Bene_Day_Srvcs,0),1) AS srvcs_per_bene_day, "
            "round(paid) paid, round(Tot_Bene_Day_Srvcs/250.0,1) AS bene_days_per_workday "
            "FROM svc WHERE Tot_Bene_Day_Srvcs>=100 AND Tot_Bene_Day_Srvcs/250.0>=40 AND Place_Of_Srvc='O' "
            f"ORDER BY bene_days_per_workday DESC LIMIT {n}"))
    finally:
        con.close()
    return _out("high_volume_services", ["bene_days_per_workday"], ["partb", "review"], rows,
                f"{len(rows)} office-setting rows where one service would need 40+ distinct patients "
                f"per working day. Review list, not a finding.")


def exclusion_list_matches():
    con = _con()
    try:
        rows = _rows(con.execute(
            "SELECT p.Rndrng_NPI npi, p.Rndrng_Prvdr_Type specialty, p.Rndrng_Prvdr_City city, "
            "round(p.Tot_Mdcr_Pymt_Amt) paid_2024, l.EXCLTYPE, l.EXCLDATE, l.REINDATE, l.GENERAL AS excl_category "
            "FROM prov p JOIN leie l ON cast(p.Rndrng_NPI AS varchar)=l.NPI ORDER BY paid_2024 DESC"))
    finally:
        con.close()
    return _out("exclusion_list_matches", [], ["partb", "q6"], rows,
                f"{len(rows)} Maryland providers in the 2024 payment file share an NPI with a current "
                f"OIG exclusion record. Needs review, not wrongdoing.")


def hospital_payment_ratios(order="lowest", limit=10):
    n = _limit(limit)
    direction = "ASC" if str(order).lower() != "highest" else "DESC"
    con = _con()
    try:
        rows = _rows(con.execute(
            "SELECT Rndrng_Prvdr_Org_Name hospital, Rndrng_Prvdr_State_Abrvtn state, Tot_Dschrgs discharges, "
            "round(Tot_Submtd_Cvrd_Chrg) charges, round(Tot_Mdcr_Pymt_Amt) medicare_paid, "
            "round(Tot_Mdcr_Pymt_Amt/NULLIF(Tot_Submtd_Cvrd_Chrg,0),3) AS paid_ratio "
            f"FROM inp WHERE Tot_Dschrgs>=500 ORDER BY paid_ratio {direction} LIMIT {n}"))
    finally:
        con.close()
    which = "lowest" if direction == "ASC" else "highest"
    return _out("hospital_payment_ratios", ["paid_ratio_hospital"], ["inp"], rows,
                f"Hospitals (500+ discharges, national FY2024) with the {which} Medicare payment-to-charge ratios.")


FUNCTIONS = {
    "metric_definitions": metric_definitions,
    "dataset_totals": dataset_totals,
    "paid_vs_submitted_by_specialty": paid_vs_submitted_by_specialty,
    "largest_gap_codes": largest_gap_codes,
    "provider_outliers_vs_peers": provider_outliers_vs_peers,
    "reconciliation_summary": reconciliation_summary,
    "high_volume_services": high_volume_services,
    "exclusion_list_matches": exclusion_list_matches,
    "hospital_payment_ratios": hospital_payment_ratios,
}

# Tool schemas for LLM function calling. The LLM may choose among these only;
# it never sees or writes SQL.
TOOL_SCHEMAS = [
    {"name": "dataset_totals", "description": "Headline totals: submitted charges, allowed, paid, provider counts (Maryland Part B 2024) and national inpatient ratio.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "paid_vs_submitted_by_specialty", "description": "Submitted vs paid by provider specialty, with gap and paid ratio. Optional exact specialty filter.",
     "parameters": {"type": "object", "properties": {
         "specialty": {"type": "string", "description": "Exact specialty name, e.g. 'Cardiology' (optional)"},
         "limit": {"type": "integer", "description": "Max rows, 1-50 (default 10)"}}}},
    {"name": "largest_gap_codes", "description": "Procedure (HCPCS) codes with the largest submitted-minus-paid gap.",
     "parameters": {"type": "object", "properties": {
         "limit": {"type": "integer", "description": "Max rows, 1-50 (default 10)"}}}},
    {"name": "provider_outliers_vs_peers", "description": "Providers paid far above their specialty peers per beneficiary (robust z-score review list).",
     "parameters": {"type": "object", "properties": {
         "limit": {"type": "integer", "description": "Max rows, 1-50 (default 10)"}}}},
    {"name": "reconciliation_summary", "description": "Whether service-level detail reconciles to provider-summary totals, and why gaps are expected.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "high_volume_services", "description": "Implausibly high daily service volumes (review list).",
     "parameters": {"type": "object", "properties": {
         "limit": {"type": "integer", "description": "Max rows, 1-50 (default 10)"}}}},
    {"name": "exclusion_list_matches", "description": "Providers whose NPI also appears on the OIG exclusion list (needs review, not wrongdoing).",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "hospital_payment_ratios", "description": "Inpatient hospitals by Medicare payment-to-charge ratio (national FY2024, 500+ discharges).",
     "parameters": {"type": "object", "properties": {
         "order": {"type": "string", "enum": ["lowest", "highest"], "description": "Which end of the ratio ranking (default lowest)"},
         "limit": {"type": "integer", "description": "Max rows, 1-50 (default 10)"}}}},
    {"name": "metric_definitions", "description": "Definitions and caveats for every metric used here.",
     "parameters": {"type": "object", "properties": {}}},
]
