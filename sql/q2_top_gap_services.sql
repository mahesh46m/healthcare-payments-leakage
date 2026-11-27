-- Q2: Which procedure codes carry the largest gap between submitted charge and payment?
SELECT HCPCS_Cd AS hcpcs, any_value(HCPCS_Desc) AS description, round(sum(sbmtd)) AS submitted, round(sum(paid)) AS paid,
       round(sum(sbmtd)-sum(paid)) AS gap, round(sum(paid)/sum(sbmtd),3) AS paid_ratio
FROM svc GROUP BY 1 ORDER BY gap DESC LIMIT 15;
