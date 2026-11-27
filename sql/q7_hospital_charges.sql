-- Q7: Inpatient hospitals nationally: covered charges vs Medicare payment.
SELECT Rndrng_Prvdr_Org_Name hospital, Rndrng_Prvdr_State_Abrvtn state, Tot_Dschrgs discharges, round(Tot_Submtd_Cvrd_Chrg) charges,
       round(Tot_Mdcr_Pymt_Amt) medicare_paid, round(Tot_Mdcr_Pymt_Amt/NULLIF(Tot_Submtd_Cvrd_Chrg,0),3) AS paid_ratio
FROM inp WHERE Tot_Dschrgs>=500 ORDER BY paid_ratio ASC LIMIT 20;
