-- Q1: Where do Medicare payments diverge from submitted charges? By provider specialty.
SELECT Rndrng_Prvdr_Type AS specialty, round(sum(sbmtd)) AS submitted, round(sum(paid)) AS paid,
       round(sum(sbmtd)-sum(paid)) AS gap, round(sum(paid)/sum(sbmtd),3) AS paid_ratio
FROM svc GROUP BY 1 HAVING sum(sbmtd)>5e6 ORDER BY gap DESC LIMIT 15;
