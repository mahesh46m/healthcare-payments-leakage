"""Run every SQL file, save CSV results and charts. Usage: python src/analyze.py"""
import duckdb, glob, json, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
os.makedirs("data/processed", exist_ok=True); os.makedirs("dashboard/img", exist_ok=True)
c = duckdb.connect(); c.execute(open("sql/00_views.sql").read())
R = {}
for f in sorted(glob.glob("sql/q*.sql")):
    name = os.path.basename(f)[:2]
    df = c.execute(open(f).read()).df(); R[name] = df
    df.to_csv(f"data/processed/{name}.csv", index=False)
M = {}
M["svc_rows"] = c.execute("select count(*) from svc").fetchone()[0]
M["providers"] = c.execute("select count(distinct Rndrng_NPI) from prov").fetchone()[0]
M["total_paid_prov"] = c.execute("select sum(Tot_Mdcr_Pymt_Amt) from prov").fetchone()[0]
t = c.execute("select sum(sbmtd), sum(allowed), sum(paid) from svc").fetchone()
M["sbmtd"], M["allowed"], M["paid"] = t
cov = c.execute("select sum(Tot_Mdcr_Pymt_Amt), sum(case when Rndrng_NPI in (select Rndrng_NPI from svc) then Tot_Mdcr_Pymt_Amt end) from prov").fetchone()
M["prov_paid"], M["prov_paid_in_svc"] = cov
M["svc_paid_total"] = M["paid"]
M["npis_no_service_rows"] = int((R["q4"]["svc_paid"] == 0).sum())
M["q4_cover_pct"] = M["paid"] / M["prov_paid"]
q3 = R["q3"]; M["q3_top_excess"] = float(q3.head(25)["excess_vs_peer_median"].sum())
M["q5_rows"] = len(R["q5"]); M["q6_matches"] = len(R["q6"]); M["q6_paid"] = float(R["q6"]["paid_2024"].sum())
q7 = R["q7"]; M["q7_min_ratio"] = float(q7["paid_ratio"].min())
M["inp_ratio_overall"] = c.execute("select sum(Tot_Mdcr_Pymt_Amt)/sum(Tot_Submtd_Cvrd_Chrg) from inp").fetchone()[0]
json.dump(M, open("data/processed/metrics.json", "w"), indent=1, default=float)
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
C1, C2 = "#1f4e79", "#c0504d"
d = R["q1"].sort_values("gap").tail(10)
fig, ax = plt.subplots(figsize=(8, 4.5)); ax.barh(d.specialty, d.gap/1e6, color=C2)
ax.set_xlabel("Submitted charges not paid by Medicare, $M (Maryland, 2024)"); ax.set_title("Q1. Where submitted charges and payments diverge")
plt.tight_layout(); plt.savefig("dashboard/img/q1_gap_by_specialty.png", dpi=150); plt.close()
d = R["q2"].sort_values("gap").tail(10); lab = d.hcpcs + " " + d.description.str.slice(0, 38)
fig, ax = plt.subplots(figsize=(8, 4.5)); ax.barh(lab, d.gap/1e6, color=C1)
ax.set_xlabel("Gap, $M"); ax.set_title("Q2. Procedure codes with the largest charge-to-payment gap")
plt.tight_layout(); plt.savefig("dashboard/img/q2_top_codes.png", dpi=150); plt.close()
d = q3.sort_values("excess_vs_peer_median", ascending=False).head(15).iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 4.5)); ax.barh([f"{sp[:24]} (#{i})" for i, sp in zip(range(len(d), 0, -1), d.specialty)], d.excess_vs_peer_median/1e6, color=C2)
ax.set_xlabel("Paid above specialty-median-per-patient, $M"); ax.set_title("Q3. Provider outliers vs specialty peers (review list)")
plt.tight_layout(); plt.savefig("dashboard/img/q3_outliers.png", dpi=150); plt.close()
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.bar(["Paid dollars in\nprovider summary", "Paid dollars visible in\nservice-level detail"], [M["prov_paid"]/1e9, M["paid"]/1e9], color=[C1, C2])
ax.set_ylabel("$B"); ax.set_title("Q4. Reconciliation: summary vs detail (Maryland, 2024)")
plt.tight_layout(); plt.savefig("dashboard/img/q4_reconciliation.png", dpi=150); plt.close()
d = R["q5"].head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 4.5)); ax.barh([f"{sp[:22]} / {h}" for sp, h in zip(d.specialty, d.HCPCS_Cd)], d.bene_days_per_workday, color=C1)
ax.set_xlabel("Patient-days of one service per working day (250 days)"); ax.set_title("Q5. Very high daily volume (review list)")
plt.tight_layout(); plt.savefig("dashboard/img/q5_volume.png", dpi=150); plt.close()
d = q7.sort_values("paid_ratio", ascending=False).iloc[::-1].head(12)
fig, ax = plt.subplots(figsize=(8, 4.5)); ax.barh(q7.hospital.str.slice(0, 34), q7.paid_ratio*100, color=C2)
ax.invert_yaxis(); ax.set_xlabel("Medicare paid as % of covered charges"); ax.set_title("Q7. Hospitals with the lowest payment-to-charge ratio")
plt.tight_layout(); plt.savefig("dashboard/img/q7_hospitals.png", dpi=150); plt.close()
print(json.dumps(M, indent=1, default=float))
