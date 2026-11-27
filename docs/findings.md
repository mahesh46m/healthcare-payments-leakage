# Findings

Real public data only. Maryland Medicare Part B (2024) plus national inpatient hospital data (FY2024) and the HHS-OIG exclusion list. Every number below is reproduced by `python src/analyze.py`.

## Q1. Paid vs submitted
Providers submitted $7.91B in charges on the 174,983 Maryland provider-service rows. Medicare paid $2.14B, or 27% of submitted. The largest gap by specialty is Ambulatory Surgical Center ($626M not paid, 19% paid ratio). Submitted charges are list prices, so the gap is mostly contractual, not lost money. The useful signal is which specialties have the widest gap.

## Q2. Codes with the biggest gap
Code 99214 (Established patient office or other outpatient visit with mo...) has the largest gap, $452M. See `data/processed/q2.csv`.

## Q3. Provider outliers vs specialty peers
Individual providers with 50+ beneficiaries, compared with the median payment per beneficiary of their own specialty (robust z-score, median absolute deviation). The 25 highest-scoring providers were paid about $84M above what the specialty median per patient would imply. These are review leads. Several are plausible for legitimate reasons (high-cost drugs, imaging or infusion mix).

## Q4. Reconciliation
The provider summary file shows $3.40B paid across 26,679 providers. The service-level detail accounts for $2.14B, or 63%. 7,447 providers appear in the summary with no service rows. CMS suppresses small cells in the service file, which likely explains much of the gap. I did not verify the full split, so treat it as a coverage limit to design around, not an error in the data.

## Q5. Implausible volume
73 provider-service rows show 40+ patient-days of the same service per working day (assuming 250 working days). Many are labs, portable X-ray and similar high-volume suppliers, where this is normal. It is a screening list, not a conclusion.

## Q6. Exclusion list matches
3 providers in the Maryland 2024 file share an NPI with an OIG exclusion record, with $280,808 paid in 2024. In each case the exclusion date is after the 2024 service year, so this does not show payment after exclusion. Needs review, not a finding of wrongdoing. Only records that list an NPI can be matched, which is a minority of the list.

## Q7. Hospital charges vs payments
Nationally, Medicare paid 17% of covered charges across inpatient hospitals in FY2024. The lowest ratio among hospitals with 500+ discharges is 3.6%.

## Limits
Maryland only for the service-level file, one year, no claim-level data, so duplicate-claim and date-of-death checks need claim files this data does not have. With real claim-level data I would add duplicate detection, overlapping-stay checks and a recovery estimate.
