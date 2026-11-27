-- Q6: Providers in the 2024 payment file whose NPI also appears on the OIG exclusion list. "Needs review", not a finding of wrongdoing:
-- the 2024 payments may pre-date the exclusion, or the match may be a data issue.
SELECT p.Rndrng_NPI npi, p.Rndrng_Prvdr_Type specialty, p.Rndrng_Prvdr_City city, round(p.Tot_Mdcr_Pymt_Amt) paid_2024,
       l.EXCLTYPE, l.EXCLDATE, l.REINDATE, l.GENERAL AS excl_category
FROM prov p JOIN leie l ON cast(p.Rndrng_NPI AS varchar)=l.NPI
ORDER BY paid_2024 DESC;
