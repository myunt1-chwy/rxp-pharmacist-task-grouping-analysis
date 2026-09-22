---
author: Mehmet Yunt
---

## Description of the Work

This work presents observational analyses addressing two questions:
whether grouping similar work makes pharmacists faster, and whether
repeated contact on the same prescription case affects call duration.

## Recommendations

1.  Separate the two research questions into individual documents. A
    single question per document would make the analysis easier to read,
    review, and comment on.
2.  The analyses compare mean durations across strata and groups. Report
    the variance, standard errors, and confidence intervals for the
    differences in means. Because DUR durations vary substantially,
    these measures are necessary to evaluate the precision and
    statistical significance of the observed differences.
3.  Explicitly name the statistical and observational methods used. This
    would help reviewers understand the analysis and avoid requiring
    them to reconstruct the methodology from the SQL.

# Remaining Work to Complete the Review

1.  Analyze the variance of call durations and the repeated-contact
    comparison. Use confidence intervals to assess whether the estimated
    70-second gain is statistically distinguishable from zero.

## Technical Appendix

### DUR Task Duration Variance

As noted in the analysis, DUR durations span a broad range, as shown in
the following table for the medications most commonly handled in DUR.

``` sql
 WITH base AS (
  SELECT USER_ID, ORDER_ID, PART_NUMBER, STARTED_AT,
         DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS SECS, ITEM_COHORT AS COH,
         CONVERT_TIMEZONE('UTC', STARTED_AT)::DATE AS D
  FROM EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE
  WHERE TASK_TYPE='DUR'
    AND TASK_CREATED_AT >= '2026-02-01' AND TASK_CREATED_AT < '2026-08-01'
    AND DWELL_IN_PROGRESS_TO_CLOSED_SECONDS IS NOT NULL
      AND USER_ID IS NOT NULL AND STARTED_AT IS NOT NULL
    AND PART_NUMBER IS NOT NULL AND ITEM_COHORT IS NOT NULL
  ), drugbench AS (
  SELECT PART_NUMBER, ROUND(MEDIAN(SECS),2) as DRUG_MEDIAN, AVG(SECS) AS DRUG_MEAN, ROUND(APPROX_PERCENTILE(SECS,0.90),2) AS DRUG_P90,  ROUND(APPROX_PERCENTILE(SECS,0.95),2) AS DRUG_P95, MAX(SECS) AS DRUG_MAX, ROUND(STDDEV(SECS),2)  as DEVIATION, COUNT(*) as cnt FROM base GROUP BY 1
)
select d.*, p.name from  drugbench d
join edldb.pdm.product p on d.part_number = p.part_number
where cnt > 10 order by cnt desc limit 10;
```

| PART<sub>NUMBER</sub> | DRUG<sub>MEDIAN</sub> | DRUG<sub>MEAN</sub> | DRUG<sub>P90</sub> | DRUG<sub>P95</sub> | DRUG<sub>MAX</sub> | DEVIATION | CNT | NAME |
|----|----|----|----|----|----|----|----|----|
| 224823 | 15.00 | 44.272828 | 71.51 | 137.83 | 3738 | 146.96 | 168194 | Simparica Trio Chewable Tablet for Dogs, 44.1-88 lbs, (Green Box), 6 Chewable Tablets (6-mos. supply) |
| 146391 | 13.00 | 41.241641 | 64.65 | 124.4 | 70157 | 263.37 | 100968 | Heartgard Plus Chew for Dogs, 51-100 lbs, (Brown Box), 6 Chews (6-mos. supply) |
| 959638 | 17.00 | 48.691905 | 82.24 | 154.19 | 3926 | 153.7 | 91488 | Apoquel (oclacitinib CHEWABLE tablet) CHEWABLE for Dogs, 16mg, 1 tablet |
| 146066 | 14.00 | 42.746453 | 68.04 | 129.29 | 10387 | 153.45 | 87459 | Bravecto CHEW for Dogs, 44-88 lbs, (Blue Box), 1 CHEW (12-wks. supply) |
| 224821 | 15.00 | 45.457729 | 73 | 139.12 | 7384 | 156.45 | 76377 | Simparica Trio Chewable Tablet for Dogs, 22.1-44.0 lbs, (Teal Box), 6 Chewable Tablets (6-mos. supply) |
| 146387 | 13.00 | 40.088312 | 65.01 | 125.56 | 3588 | 136.37 | 72414 | Heartgard Plus Chew for Dogs, up to 25 lbs, (Blue Box), 6 Chews (6-mos. supply) |
| 146412 | 13.00 | 40.035052 | 63.41 | 123.48 | 4578 | 142.47 | 71837 | NexGard Chewables for Dogs, 60.1-121 lbs, (Red Box), 6 Chewable Tablets (6-mos. supply) |
| 146409 | 13.00 | 40.143940 | 63.18 | 120.68 | 4383 | 144.01 | 71523 | NexGard Chewables for Dogs, 24.1-60 lbs, (Purple Box), 6 Chewable Tablets (6-mos. supply) |
| 224819 | 15.00 | 45.672822 | 73.99 | 138.65 | 5933 | 159.78 | 69647 | Simparica Trio Chewable Tablet for Dogs, 11.1-22.0 lbs, (Caramel Box), 6 Chewable Tablets (6-mos. supply) |
| 146204 | 16.00 | 47.444060 | 79.46 | 149.38 | 6164 | 154.09 | 67268 | Apoquel (oclacitinib) TABLETS for Dogs, 16-mg, 1 tablet |

The situation is similar for DUR tasks that were successfully approved
and were not refills.

``` sql
WITH base AS (
  SELECT USER_ID, ORDER_ID, PART_NUMBER, STARTED_AT,
         DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS SECS, ITEM_COHORT AS COH,
         CONVERT_TIMEZONE('UTC', STARTED_AT)::DATE AS D
  FROM EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE
  WHERE TASK_TYPE='DUR'
    AND TASK_CREATED_AT >= '2026-02-01' AND TASK_CREATED_AT < '2026-08-01'
    AND DWELL_IN_PROGRESS_TO_CLOSED_SECONDS IS NOT NULL
    -- AND DWELL_IN_PROGRESS_TO_CLOSED_SECONDS BETWEEN 0 and 300
    AND USER_ID IS NOT NULL AND STARTED_AT IS NOT NULL
    AND PART_NUMBER IS NOT NULL AND ITEM_COHORT IS NOT NULL
    AND USAGE_STATE='APPROVED'
    AND IS_REFILL = FALSE
    AND HANDOFF_TYPE is NULL
), raw AS (
  SELECT PART_NUMBER, ROUND(MEDIAN(SECS),2) as DRUG_MEDIAN, AVG(SECS) AS DRUG_MEAN, ROUND(APPROX_PERCENTILE(SECS,0.90),2) AS DRUG_P90,  ROUND(APPROX_PERCENTILE(SECS,0.95),2) AS DRUG_P95, MAX(SECS) AS DRUG_MAX, ROUND(STDDEV(SECS),2)  as DEVIATION, COUNT(*) as cnt FROM base GROUP BY 1
),
drugbench as (
SELECT b.PART_NUMBER, ROUND(MEDIAN(SECS),2) as DRUG_MEDIAN, AVG(SECS) AS DRUG_MEAN, ROUND(APPROX_PERCENTILE(SECS,0.90),2) AS DRUG_P90,  ROUND(APPROX_PERCENTILE(SECS,0.95),2) AS DRUG_P95, MAX(SECS) AS DRUG_MAX, ROUND(STDDEV(SECS),2)  as DEVIATION, COUNT(*) as cnt FROM base b join raw
d on b.part_number = d.part_number where secs < d.drug_p95
GROUP BY 1
)
select d.*, p.name from  drugbench d
join edldb.pdm.product p on d.part_number = p.part_number
where cnt > 10 order by cnt desc limit 10;
```

| PART<sub>NUMBER</sub> | DRUG<sub>MEDIAN</sub> | DRUG<sub>MEAN</sub> | DRUG<sub>P90</sub> | DRUG<sub>P95</sub> | DRUG<sub>MAX</sub> | DEVIATION | CNT | NAME |
|----|----|----|----|----|----|----|----|----|
| 224823 | 15.00 | 43.483041 | 68.89 | 133.01 | 3738 | 146.52 | 165282 | Simparica Trio Chewable Tablet for Dogs, 44.1-88 lbs, (Green Box), 6 Chewable Tablets (6-mos. supply) |
| 146391 | 13.00 | 40.236652 | 61.5 | 118.45 | 70157 | 264.58 | 99002 | Heartgard Plus Chew for Dogs, 51-100 lbs, (Brown Box), 6 Chews (6-mos. supply) |
| 959638 | 16.00 | 46.708887 | 77.06 | 145.25 | 3926 | 151.14 | 87880 | Apoquel (oclacitinib CHEWABLE tablet) CHEWABLE for Dogs, 16mg, 1 tablet |
| 146066 | 14.00 | 41.498585 | 64.33 | 123.28 | 10387 | 152.18 | 85157 | Bravecto CHEW for Dogs, 44-88 lbs, (Blue Box), 1 CHEW (12-wks. supply) |
| 224821 | 15.00 | 44.598326 | 70.31 | 133.31 | 7384 | 156.23 | 74924 | Simparica Trio Chewable Tablet for Dogs, 22.1-44.0 lbs, (Teal Box), 6 Chewable Tablets (6-mos. supply) |
| 146387 | 13.00 | 39.189112 | 62 | 120.25 | 3588 | 135.74 | 70995 | Heartgard Plus Chew for Dogs, up to 25 lbs, (Blue Box), 6 Chews (6-mos. supply) |
| 146412 | 13.00 | 39.062899 | 60.45 | 118.29 | 4578 | 141.41 | 70415 | NexGard Chewables for Dogs, 60.1-121 lbs, (Red Box), 6 Chewable Tablets (6-mos. supply) |
| 146409 | 13.00 | 38.989097 | 60.12 | 115.59 | 4383 | 142.47 | 69887 | NexGard Chewables for Dogs, 24.1-60 lbs, (Purple Box), 6 Chewable Tablets (6-mos. supply) |
| 224819 | 15.00 | 44.985984 | 70.8 | 133.71 | 5933 | 160.26 | 68208 | Simparica Trio Chewable Tablet for Dogs, 11.1-22.0 lbs, (Caramel Box), 6 Chewable Tablets (6-mos. supply) |
| 146204 | 16.00 | 45.807565 | 74.02 | 140.29 | 6164 | 153.41 | 64879 | Apoquel (oclacitinib) TABLETS for Dogs, 16-mg, 1 tablet |

The data raise the question of why a successful approval for a
medication such as Simparica Trio, for which a dosage has already been
prescribed, takes more than two minutes. Possible explanations include
multitasking and other factors not captured in the data.

Parts of the analysis have been redone using truncated DUR task
durations. As an initial approach, durations are limited to each
medication's 95th-percentile value, and the analysis includes only tasks
with successful approvals. The truncated statistics for the ten most
common medications follow:

``` sql
WITH base AS (
    SELECT USER_ID, ORDER_ID, PART_NUMBER, STARTED_AT,
           DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS SECS, ITEM_COHORT AS COH,
           CONVERT_TIMEZONE('UTC', STARTED_AT)::DATE AS D
    FROM EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE
    WHERE TASK_TYPE='DUR'
      AND TASK_CREATED_AT >= '2026-02-01' AND TASK_CREATED_AT < '2026-08-01'
      AND DWELL_IN_PROGRESS_TO_CLOSED_SECONDS IS NOT NULL
      -- AND DWELL_IN_PROGRESS_TO_CLOSED_SECONDS BETWEEN 0 and 300
      AND USER_ID IS NOT NULL AND STARTED_AT IS NOT NULL
      AND PART_NUMBER IS NOT NULL AND ITEM_COHORT IS NOT NULL
      AND USAGE_STATE='APPROVED'
      AND IS_REFILL = FALSE
      AND HANDOFF_TYPE is NULL
  ), raw AS (
    SELECT PART_NUMBER, ROUND(MEDIAN(SECS),2) as DRUG_MEDIAN, AVG(SECS) AS DRUG_MEAN, ROUND(APPROX_PERCENTILE(SECS,0.90),2) AS DRUG_P90,  ROUND(APPROX_PERCENTILE(SECS,0.95),2) AS DRUG_P95, MAX(SECS) AS DRUG_MAX, ROUND(STDDEV(SECS),2)  as DEVIATION, COUNT(*) as cnt FROM base GROUP BY 1
  ),
  drugbench as (
  SELECT b.PART_NUMBER, ROUND(MEDIAN(SECS),2) as DRUG_MEDIAN, AVG(SECS) AS DRUG_MEAN, ROUND(APPROX_PERCENTILE(SECS,0.90),2) AS DRUG_P90,  ROUND(APPROX_PERCENTILE(SECS,0.95),2) AS DRUG_P95, MAX(SECS) AS DRUG_MAX, ROUND(STDDEV(SECS),2)  as DEVIATION, COUNT(*) as cnt FROM base b join raw
  d on b.part_number = d.part_number where secs < d.drug_p95
  GROUP BY 1
  )
  select d.*, p.name from  drugbench d
  join edldb.pdm.product p on d.part_number = p.part_number
  where cnt > 10 order by cnt desc limit 10
```

| PART<sub>NUMBER</sub> | DRUG<sub>MEDIAN</sub> | DRUG<sub>MEAN</sub> | DRUG<sub>P90</sub> | DRUG<sub>P95</sub> | DRUG<sub>MAX</sub> | DEVIATION | CNT | NAME |
|----|----|----|----|----|----|----|----|----|
| 224823 | 14.00 | 21.826935 | 50 | 70.29 | 132 | 22.12 | 156993 | Simparica Trio Chewable Tablet for Dogs, 44.1-88 lbs, (Green Box), 6 Chewable Tablets (6-mos. supply) |
| 146391 | 12.00 | 19.454904 | 44 | 63 | 118 | 19.76 | 94055 | Heartgard Plus Chew for Dogs, 51-100 lbs, (Brown Box), 6 Chews (6-mos. supply) |
| 959638 | 15.00 | 24.084943 | 55.91 | 78.86 | 145 | 24.56 | 83491 | Apoquel (oclacitinib CHEWABLE tablet) CHEWABLE for Dogs, 16mg, 1 tablet |
| 146066 | 13.00 | 20.447353 | 46 | 66.01 | 123 | 20.49 | 80898 | Bravecto CHEW for Dogs, 44-88 lbs, (Blue Box), 1 CHEW (12-wks. supply) |
| 224821 | 14.00 | 22.220213 | 51 | 71.91 | 133 | 22.5 | 71181 | Simparica Trio Chewable Tablet for Dogs, 22.1-44.0 lbs, (Teal Box), 6 Chewable Tablets (6-mos. supply) |
| 146387 | 13.00 | 19.607970 | 44.03 | 63.32 | 120 | 19.96 | 67454 | Heartgard Plus Chew for Dogs, up to 25 lbs, (Blue Box), 6 Chews (6-mos. supply) |
| 146412 | 12.00 | 19.209635 | 43 | 62 | 118 | 19.54 | 66902 | NexGard Chewables for Dogs, 60.1-121 lbs, (Red Box), 6 Chewable Tablets (6-mos. supply) |
| 146409 | 12.00 | 19.060988 | 43 | 61.6 | 115 | 19.13 | 66390 | NexGard Chewables for Dogs, 24.1-60 lbs, (Purple Box), 6 Chewable Tablets (6-mos. supply) |
| 224819 | 14.00 | 22.185066 | 51 | 72.47 | 133 | 22.7 | 64793 | Simparica Trio Chewable Tablet for Dogs, 11.1-22.0 lbs, (Caramel Box), 6 Chewable Tablets (6-mos. supply) |
| 146204 | 15.00 | 23.401019 | 54 | 75.97 | 140 | 23.76 | 61643 | Apoquel (oclacitinib) TABLETS for Dogs, 16-mg, 1 tablet |

# Analysis of Task Composition

We reran the task-composition and ordering analyses using truncated
durations, considering only DUR tasks with durations below the
95th-percentile value. The conclusion does not change.

``` sql
WITH base AS (
  SELECT USER_ID, ORDER_ID, PART_NUMBER, STARTED_AT,
         DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS SECS, ITEM_COHORT AS COH,
         CONVERT_TIMEZONE('UTC', STARTED_AT)::DATE AS D
  FROM EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE
  WHERE TASK_TYPE='DUR'
    AND TASK_CREATED_AT >= '2026-02-01' AND TASK_CREATED_AT < '2026-08-01'
    AND DWELL_IN_PROGRESS_TO_CLOSED_SECONDS IS NOT NULL
    AND USER_ID IS NOT NULL AND STARTED_AT IS NOT NULL
    AND PART_NUMBER IS NOT NULL AND ITEM_COHORT IS NOT NULL
  ), raw AS (
    SELECT PART_NUMBER, ROUND(MEDIAN(SECS),2) as DRUG_MEDIAN, AVG(SECS) AS DRUG_MEAN, ROUND(APPROX_PERCENTILE(SECS,0.90),2) AS DRUG_P90,  ROUND(APPROX_PERCENTILE(SECS,0.95),2) AS DRUG_P95, MAX(SECS) AS DRUG_MAX, ROUND(STDDEV(SECS),2)  as DEVIATION, COUNT(*) as cnt FROM base GROUP BY 1
  ),
  drugbench as (
  SELECT b.PART_NUMBER, ROUND(MEDIAN(SECS),2) as DRUG_MEDIAN, AVG(SECS) AS DRUG_MEAN, ROUND(APPROX_PERCENTILE(SECS,0.90),2) AS DRUG_P90,  ROUND(APPROX_PERCENTILE(SECS,0.95),2) AS DRUG_P95, MAX(SECS) AS DRUG_MAX, ROUND(STDDEV(SECS),2)  as DEVIATION, COUNT(*) as cnt FROM base b join raw
  d on b.part_number = d.part_number where secs < d.drug_p95
  GROUP BY 1
), ded AS (
  SELECT * FROM (SELECT b.*, ROW_NUMBER() OVER
                 (PARTITION BY USER_ID, ORDER_ID ORDER BY STARTED_AT) RN
                 FROM base b join raw r on r.part_number = b.part_number where b.secs < r.drug_p95) WHERE RN = 1
), s AS (
  SELECT *, LAG(COH) OVER (PARTITION BY USER_ID ORDER BY STARTED_AT) AS PCOH FROM ded
), r AS (
  SELECT *, SUM(IFF(PCOH=COH,0,1)) OVER (PARTITION BY USER_ID ORDER BY STARTED_AT
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS RUN_ID
  FROM s
), p AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY USER_ID, RUN_ID ORDER BY STARTED_AT) AS POS,
            COUNT(*)     OVER (PARTITION BY USER_ID, RUN_ID) AS RUN_LEN
  FROM r
), g AS (
  SELECT p.USER_ID, p.D, p.COH, p.SECS, db.DRUG_MEAN,
         CASE WHEN RUN_LEN = 1 THEN '1_ISOLATED'
              WHEN POS = 1 THEN '2_RUN_START'
              WHEN POS = 2 THEN '3_POS_2'
              WHEN POS = 3 THEN '4_POS_3'
              WHEN POS BETWEEN 4 AND 6 THEN '5_POS_4_6'
              ELSE '6_POS_7PLUS' END AS GRP
  FROM p JOIN drugbench db ON db.PART_NUMBER = p.PART_NUMBER
), both AS (
  SELECT USER_ID, D, COH FROM g GROUP BY 1,2,3
  HAVING SUM(IFF(GRP='1_ISOLATED',1,0)) > 0 AND SUM(IFF(GRP<>'1_ISOLATED',1,0)) > 0
), f AS (
  SELECT g.* FROM g JOIN both b ON b.USER_ID=g.USER_ID AND b.D=g.D AND b.COH=g.COH
)
SELECT GRP, COUNT(*) AS TASKS,
  ROUND(SUM(SECS)/COUNT(*),1) AS AHT_S, MEDIAN(SECS) AS AHT_MED_S,
  ROUND(SUM(DRUG_MEAN)/COUNT(*),1) AS EXPECTED_FROM_DRUG_MIX_S,
  ROUND(SUM(SECS)/NULLIF(SUM(DRUG_MEAN),0),4) AS DRUG_ADJ_INDEX
FROM f GROUP BY 1 ORDER BY 1
```

| GRP | TASKS | AHT<sub>S</sub> | AHT<sub>MED</sub>\_S | EXPECTED<sub>FROM</sub>\_DRUG<sub>MIX</sub>\_S | DRUG<sub>ADJ</sub>\_INDEX |
|----|----|----|----|----|----|
| 1<sub>ISOLATED</sub> | 1004705 | 30.2 | 18.000 | 30.2 | 0.9999 |
| 2<sub>RUN</sub>\_START | 790756 | 27.2 | 16.000 | 26.7 | 1.0182 |
| 3<sub>POS</sub>\_2 | 790749 | 27.0 | 16.000 | 26.7 | 1.0118 |
| 4<sub>POS</sub>\_3 | 377739 | 26.1 | 16.000 | 25.8 | 1.0107 |
| 5<sub>POS</sub>\_4<sub>6</sub> | 338829 | 25.1 | 15.000 | 25.0 | 1.0066 |
| 6<sub>POS</sub>\_7PLUS | 66760 | 24.5 | 15.000 | 24.6 | 0.9975 |

## Reference

1.  [ Would Grouping Similar Work Make Pharmacists Faster? What the data
    says](https://chewyinc.atlassian.net/wiki/x/hYRyRQE )
2.  [«doc2» Methods, queries and full results: pharmacist task grouping
    analysis](https://chewyinc.atlassian.net/wiki/x/Rg5NRQE)
