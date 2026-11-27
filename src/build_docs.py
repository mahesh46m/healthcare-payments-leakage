import json, pandas as pd
M = json.load(open("data/processed/metrics.json"))
q = {k: pd.read_csv(f"data/processed/{k}.csv") for k in ["q1","q2","q3","q4","q5","q6","q7"]}
B = lambda x: f"${x/1e9:.2f}B"; Mi = lambda x: f"${x/1e6:,.0f}M"
gap = M["sbmtd"] - M["paid"]
s = {
 "paid_ratio": M["paid"]/M["sbmtd"], "gap": gap,
 "top_spec": q["q1"].sort_values("gap", ascending=False).iloc[0],
 "top_code": q["q2"].iloc[0],
}
F = f"""# Findings

Real public data only. Maryland Medicare Part B (2024) plus national inpatient hospital data (FY2024) and the HHS-OIG exclusion list. Every number below is reproduced by `python src/analyze.py`.

## Q1. Paid vs submitted
Providers submitted {B(M['sbmtd'])} in charges on the {M['svc_rows']:,} Maryland provider-service rows. Medicare paid {B(M['paid'])}, or {s['paid_ratio']:.0%} of submitted. The largest gap by specialty is {s['top_spec'].specialty} ({Mi(s['top_spec'].gap)} not paid, {s['top_spec'].paid_ratio:.0%} paid ratio). Submitted charges are list prices, so the gap is mostly contractual, not lost money. The useful signal is which specialties have the widest gap.

## Q2. Codes with the biggest gap
Code {s['top_code'].hcpcs} ({s['top_code'].description[:60]}...) has the largest gap, {Mi(s['top_code'].gap)}. See `data/processed/q2.csv`.

## Q3. Provider outliers vs specialty peers
Individual providers with 50+ beneficiaries, compared with the median payment per beneficiary of their own specialty (robust z-score, median absolute deviation). The 25 highest-scoring providers were paid about {Mi(M['q3_top_excess'])} above what the specialty median per patient would imply. These are review leads. Several are plausible for legitimate reasons (high-cost drugs, imaging or infusion mix).

## Q4. Reconciliation
The provider summary file shows {B(M['prov_paid'])} paid across {M['providers']:,} providers. The service-level detail accounts for {B(M['svc_paid_total'])}, or {M['q4_cover_pct']:.0%}. {M['npis_no_service_rows']:,} providers appear in the summary with no service rows. CMS suppresses small cells in the service file, which likely explains much of the gap. I did not verify the full split, so treat it as a coverage limit to design around, not an error in the data.

## Q5. Implausible volume
{M['q5_rows']} provider-service rows show 40+ patient-days of the same service per working day (assuming 250 working days). Many are labs, portable X-ray and similar high-volume suppliers, where this is normal. It is a screening list, not a conclusion.

## Q6. Exclusion list matches
{M['q6_matches']} providers in the Maryland 2024 file share an NPI with an OIG exclusion record, with {Mi(M['q6_paid']) if M['q6_paid']>=1e6 else '$'+format(round(M['q6_paid']),',')} paid in 2024. In each case the exclusion date is after the 2024 service year, so this does not show payment after exclusion. Needs review, not a finding of wrongdoing. Only records that list an NPI can be matched, which is a minority of the list.

## Q7. Hospital charges vs payments
Nationally, Medicare paid {M['inp_ratio_overall']:.0%} of covered charges across inpatient hospitals in FY2024. The lowest ratio among hospitals with 500+ discharges is {M['q7_min_ratio']:.1%}.

## Limits
Maryland only for the service-level file, one year, no claim-level data, so duplicate-claim and date-of-death checks need claim files this data does not have. With real claim-level data I would add duplicate detection, overlapping-stay checks and a recovery estimate.
"""
open("docs/findings.md","w").write(F)
R = f"""# Healthcare Payments Analysis

How do Medicare dollars move from charges to payments? A SQL and Python analysis of real, public Medicare payment data and the federal exclusion list.

![Charge vs payment gap by specialty](dashboard/img/q1_gap_by_specialty.png)

## Business question
Billed charges, allowed amounts and actual payments differ. Where are the gaps, which providers look unusual against their peers, and does the data reconcile end to end?

## Data (all real, all public)
| Source | Use |
|---|---|
| CMS Medicare Physician & Other Practitioners, by Provider and Service (2024), Maryland | Charge vs payment, outliers, volume |
| CMS Medicare Physician & Other Practitioners, by Provider (2024), Maryland | Provider totals, reconciliation |
| CMS Medicare Inpatient Hospitals, by Provider (FY2024), national | Hospital charge vs payment |
| HHS-OIG List of Excluded Individuals/Entities | Exclusion matching by NPI |

No synthetic data. Raw files are not committed; `src/download.py` fetches them.

## Headline numbers
- {B(M['sbmtd'])} submitted vs {B(M['paid'])} paid ({s['paid_ratio']:.0%}) on {M['svc_rows']:,} Maryland provider-service rows.
- Service detail covers {M['q4_cover_pct']:.0%} of provider-summary payments, so any bottom-up analysis undercounts.
- {M['q6_matches']} Maryland providers share an NPI with an exclusion record (exclusion dated after the 2024 service year; needs review, not wrongdoing).
- Medicare paid {M['inp_ratio_overall']:.0%} of covered charges nationally for inpatient hospitals.

Full write-up: [docs/findings.md](docs/findings.md)

## Questions
1. Q1 paid vs submitted by specialty
2. Q2 codes with the largest gap
3. Q3 provider outliers vs specialty peers
4. Q4 reconciliation of summary vs detail
5. Q5 very high daily volume
6. Q6 exclusion-list matches
7. Q7 hospital charge-to-payment ratio

Each question is one file in `sql/`. Results land in `data/processed/` and charts in `dashboard/img/`.

## Run it
```
pip install pandas duckdb matplotlib
python src/download.py
python src/analyze.py
```

## Limitations
One state and one year for physician data. Aggregated data, so no duplicate-claim or date-of-death checks. Flags are screening leads and not accusations.

Built by Mahesh M.
"""
open("README.md","w").write(R)
