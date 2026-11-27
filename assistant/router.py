"""Deterministic question -> function router.

This is the default answering path when no LLM API key is configured, and the
fallback when the LLM is unavailable. It maps a natural-language question to
one of the allowlisted query functions (or None when the question is out of
scope). The LLM path uses the same allowlist through tool calling; neither path
ever runs free-text SQL.
"""
import re

# (function, [keyword groups]); a rule scores when ANY group matches.
# A group is a tuple of alternatives: the group matches when ANY alternative's
# regex appears in the question. Rules are scored; highest score wins.
RULES = [
    ("metric_definitions", 3, [
        (r"\b(define|definition|meaning|mean|explain)\b.*\b(metric|ratio|z.?score|gap|allowed|submitted|caveat)\b",
         r"\bwhat do(es)?\b.*\bmean\b"),
    ]),
    ("exclusion_list_matches", 3, [
        (r"\bexclu", r"\boig\b", r"\bleie\b", r"\bbanned\b", r"\bbarred\b"),
    ]),
    ("reconciliation_summary", 3, [
        (r"\breconcil", r"\bsummary\b.*\bdetail\b", r"\bdetail\b.*\bsummary\b",
         r"\bcover(age|s)?\b.*\b(detail|summary|total)"),
    ]),
    ("high_volume_services", 3, [
        (r"\b(implausib|impossible|unrealistic)", r"\bhigh[- ]volume\b",
         r"\bvolume\b.*\b(flag|review|suspicious|weird|odd)\b", r"\bdaily volume\b",
         r"\btoo many\b.*\b(service|patient|bene)"),
    ]),
    ("provider_outliers_vs_peers", 3, [
        (r"\boutlier", r"\babove\b.*\bpeer", r"\bpeer\b.*\b(median|comparison|compare)",
         r"\bfar above\b", r"\bz.?score\b"),
    ]),
    ("hospital_payment_ratios", 3, [
        (r"\bhospital", r"\binpatient\b"),
    ]),
    ("largest_gap_codes", 3, [
        (r"\bhcpcs\b", r"\bprocedure code", r"\bcodes?\b.*\bgap\b", r"\bgap\b.*\bcodes?\b"),
    ]),
    ("paid_vs_submitted_by_specialty", 2, [
        (r"\bspecialt", r"\bpaid\b.*\bsubmitted\b", r"\bsubmitted\b.*\bpaid\b",
         r"\bcharge\b.*\bpay", r"\bpay\b.*\bcharge"),
    ]),
    ("dataset_totals", 3, [
        (r"\boverall\b", r"\btotal", r"\bheadline\b", r"\bhow much\b.*\bpay",
         r"\bhow many\b.*\bprovider", r"\bsummari[sz]e\b.*\bdata"),
    ]),
]

_OUT_OF_SCOPE = re.compile(
    r"\b(weather|stock|sports?|news|recipe|movie|music|joke|covid vaccine appointment)\b", re.I)


def route(question, specialties=None):
    """Return (function_name, params) or (None, reason) for out-of-scope questions."""
    q = (question or "").strip()
    if not q:
        return None, "empty question"
    if _OUT_OF_SCOPE.search(q):
        return None, "out of scope: this assistant only answers questions about the Medicare payment dataset"
    best, best_score = None, 0
    for fn, weight, groups in RULES:
        score = 0
        for group in groups:
            if any(re.search(alt, q, re.I) for alt in group):
                score += weight
        if score > best_score:
            best, best_score = fn, score
    if best is None:
        return None, ("no matching topic: try asking about totals, specialties, procedure codes, "
                      "provider outliers, reconciliation, high daily volumes, exclusion-list matches, "
                      "or hospital payment ratios")
    params = {}
    m = re.search(r"\btop\s+(\d{1,2})\b", q, re.I)
    if m and best in {"paid_vs_submitted_by_specialty", "largest_gap_codes",
                      "provider_outliers_vs_peers", "high_volume_services", "hospital_payment_ratios"}:
        params["limit"] = int(m.group(1))
    if best == "hospital_payment_ratios" and re.search(r"\b(highest|most|best|largest|top)\b", q, re.I):
        params["order"] = "highest"
    if best == "paid_vs_submitted_by_specialty" and specialties:
        for sp in specialties:
            if re.search(r"\b" + re.escape(sp) + r"s?\b", q, re.I):
                params["specialty"] = sp
                break
    return best, params
