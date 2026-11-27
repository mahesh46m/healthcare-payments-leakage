-- Q5: Implausible activity: many services per beneficiary-day, or very high daily volume.
SELECT Rndrng_NPI npi, Rndrng_Prvdr_Type specialty, HCPCS_Cd, HCPCS_Desc, Tot_Srvcs, Tot_Bene_Day_Srvcs,
       round(Tot_Srvcs/NULLIF(Tot_Bene_Day_Srvcs,0),1) AS srvcs_per_bene_day, round(paid) paid,
       round(Tot_Bene_Day_Srvcs/250.0,1) AS bene_days_per_workday
FROM svc WHERE Tot_Bene_Day_Srvcs>=100 AND Tot_Bene_Day_Srvcs/250.0>=40 AND Place_Of_Srvc='O'
ORDER BY bene_days_per_workday DESC LIMIT 100;
