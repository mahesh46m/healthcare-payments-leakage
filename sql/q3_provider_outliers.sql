-- Q3: Providers whose Medicare payment per beneficiary is far above specialty peers (robust z-score).
WITH base AS (
  SELECT Rndrng_NPI npi, Rndrng_Prvdr_Type specialty, Rndrng_Prvdr_City city, Tot_Mdcr_Pymt_Amt pay, Tot_Benes benes,
         Tot_Mdcr_Pymt_Amt/NULLIF(Tot_Benes,0) AS pay_per_bene
  FROM prov WHERE Tot_Benes>=50 AND Rndrng_Prvdr_Ent_Cd='I'),
stats AS (SELECT specialty, count(*) n, median(pay_per_bene) med, median(abs(pay_per_bene-(SELECT 0))) x FROM base GROUP BY 1),
mad AS (SELECT b.specialty, median(abs(b.pay_per_bene-s.med)) AS mad, any_value(s.med) med, any_value(s.n) n FROM base b JOIN stats s USING(specialty) GROUP BY 1)
SELECT b.npi, b.specialty, b.city, round(b.pay) AS total_paid, b.benes, round(b.pay_per_bene) AS pay_per_bene, round(m.med) AS peer_median,
       round(0.6745*(b.pay_per_bene-m.med)/NULLIF(m.mad,0),1) AS robust_z, round(b.pay-b.benes*m.med) AS excess_vs_peer_median
FROM base b JOIN mad m USING(specialty) WHERE m.n>=30 ORDER BY robust_z DESC LIMIT 200;
