-- Q4: Do service-level payments reconcile to provider-level totals? Rows with a gap are listed (CMS suppresses small cells, so gaps are expected).
WITH a AS (SELECT Rndrng_NPI npi, sum(paid) svc_paid FROM svc GROUP BY 1),
     b AS (SELECT Rndrng_NPI npi, Tot_Mdcr_Pymt_Amt prov_paid FROM prov)
SELECT b.npi, round(b.prov_paid) prov_paid, round(coalesce(a.svc_paid,0)) svc_paid,
       round(b.prov_paid-coalesce(a.svc_paid,0)) AS unreconciled, round((b.prov_paid-coalesce(a.svc_paid,0))/NULLIF(b.prov_paid,0),3) AS pct
FROM b LEFT JOIN a USING(npi) ORDER BY abs(unreconciled) DESC;
