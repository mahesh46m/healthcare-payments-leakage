CREATE OR REPLACE VIEW svc AS SELECT *, Tot_Srvcs*Avg_Sbmtd_Chrg AS sbmtd, Tot_Srvcs*Avg_Mdcr_Alowd_Amt AS allowed, Tot_Srvcs*Avg_Mdcr_Pymt_Amt AS paid FROM read_csv_auto('data/raw/partb_provider_service_md_2024.csv');
CREATE OR REPLACE VIEW prov AS SELECT * FROM read_csv_auto('data/raw/partb_provider_md_2024.csv');
CREATE OR REPLACE VIEW inp AS SELECT * FROM read_csv_auto('data/raw/inpatient_provider_fy2024.csv');
CREATE OR REPLACE VIEW leie AS SELECT * FROM read_csv_auto('data/raw/leie.csv', all_varchar=true);
