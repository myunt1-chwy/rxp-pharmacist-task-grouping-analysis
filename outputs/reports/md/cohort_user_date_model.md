# Cohort/pet-type/user/date fixed-effects model

## Sample and indicators

The source is `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS`. Eligible valid-DUR tasks have a user,
task, process start, positive imputed dwell duration, and valid `COHORT_SEQN`
and `COHORT_BATCH_LEN` values (both at least one; sequence at most batch length).
One global `APPROX_PERCENTILE(DURATION_SECONDS, 0.95)` cutoff is calculated
before retaining tasks with duration strictly below it. The valid-DUR pipeline
starts a new cohort batch when valid tasks are not consecutive, the break is at
least one hour, or the cohort changes. Missing cohort, pet type, approval
channel, and prescription source are represented by `<Missing>`.

For cohort sequence number $S_i$, cohort batch length $L_i$, and correction
count $N_i$, define

$$
P_i=\mathbf{1}(L_i>1\land S_i>1),\quad
F_i=\mathbf{1}(L_i>1\land S_i<L_i),\quad
C_i=\mathbf{1}(N_i>0).
$$

These are `SAME_PRECEDING`, the `SAME_FOLLOWING` placebo, and `HAS_CORRECTION`.
Each task's positive duration $Y_i$ receives one global Box-Cox transform
$Z_i=g_\lambda(Y_i)=(Y_i^\lambda-1)/\lambda$ (or $\log Y_i$ when
$\lambda=0$). The fitted $\widehat{\lambda}$ is -0.08159843.

## Model formula

Let $c(i)=(\mathrm{COH}_i,\mathrm{PETTYPE}_i,\mathrm{USER\_ID}_i,D_i)$
be the fixed cell, $A_i$ the approval channel, and $R_i$ the prescription
source. The model is

$$
\begin{aligned}
Z_i={}&\gamma_{c(i)}+\beta_P P_i+\beta_F F_i+\beta_C C_i\\
&+\sum_{a\ne a_0}\theta_a\mathbf{1}(A_i=a)
 +\sum_{s\ne s_0}\phi_s\mathbf{1}(R_i=s)\\
&+\epsilon_i.
\end{aligned}
$$

There is one fixed effect per observed `(COH, PETTYPE, USER_ID, D)` cell and
no overall intercept. Each cell has its own intercept; there is no shared
date effect. Weekday contrasts are determined by date and therefore absorbed
by the cells. Pet type is likewise absorbed. The categorical references are
`PH` for approval channel and
`PRACTICE_HUB` for prescription source (the most
frequent level, with lexicographic tie breaking). The model has no random
effects: $\epsilon_i\sim N(0,\sigma_e^2)$ independently. OLS estimates fixed
effects; the residual SD interval uses a chi-square approximation. Wald 95%
confidence intervals and two-sided normal p-values are reported for fixed
effects. Estimates and diagnostics are on the Box-Cox scale.

## Sample and fit

| Quantity | Value |
|---|---:|
| Tasks | 3,433,218 |
| Cohort/pet-type/user/date cells | 139,104 |
| Users | 340 |
| Dates | 182 |
| Global approximate P95 cutoff (seconds) | 156.608019 |
| Box-Cox lambda | -0.08159843 |
| Conditional R-squared | 0.362179 |
| Conditional RMSE | 0.579889 |
| Restricted negative log-likelihood | 3085297.435993 |
| Converged | True |

## Fixed effects

| Term | Estimate | SE | z | p-value | 95% CI | Significant |
|---|---:|---:|---:|---:|---:|:---:|
| SAME_PRECEDING | -0.029075 | 0.000673 | -43.1789 | <1e-300 | [-0.030394, -0.027755] | Yes |
| SAME_FOLLOWING | -0.001206 | 0.000673 | -1.7912 | 0.0732547 | [-0.002526, 0.000114] | No |
| HAS_CORRECTION | 0.286993 | 0.000795 | 360.8716 | <1e-300 | [0.285434, 0.288552] | Yes |
| APPROVAL_CHANNEL[CLINIC_EMAIL vs PH] | 0.237636 | 0.045441 | 5.2295 | 1.69934e-07 | [0.148573, 0.326699] | Yes |
| APPROVAL_CHANNEL[CUSTOMER_MAIL vs PH] | 0.476225 | 0.013202 | 36.0711 | 6.42948e-285 | [0.450349, 0.502101] | Yes |
| APPROVAL_CHANNEL[DIGITAL vs PH] | 0.153455 | 0.040544 | 3.7849 | 0.00015377 | [0.073990, 0.232919] | Yes |
| APPROVAL_CHANNEL[FAX vs PH] | 0.204661 | 0.011362 | 18.0133 | 1.53259e-72 | [0.182392, 0.226929] | Yes |
| APPROVAL_CHANNEL[PARTNER vs PH] | -0.042729 | 0.007965 | -5.3643 | 8.12608e-08 | [-0.058341, -0.027117] | Yes |
| APPROVAL_CHANNEL[RHAPSODY vs PH] | 0.105194 | 0.053068 | 1.9823 | 0.0474511 | [0.001183, 0.209206] | Yes |
| APPROVAL_CHANNEL[VERBAL vs PH] | -0.007503 | 0.010793 | -0.6951 | 0.486966 | [-0.028656, 0.013651] | No |
| APPROVAL_CHANNEL[VET vs PH] | 0.021814 | 0.106840 | 0.2042 | 0.838213 | [-0.187588, 0.231217] | No |
| PRESCRIPTION_SOURCE[CLINIC_EMAIL vs PRACTICE_HUB] | -0.003203 | 0.011315 | -0.2831 | 0.777095 | [-0.025381, 0.018974] | No |
| PRESCRIPTION_SOURCE[CS_FIRST_CONTACT vs PRACTICE_HUB] | -0.211988 | 0.210372 | -1.0077 | 0.313606 | [-0.624309, 0.200332] | No |
| PRESCRIPTION_SOURCE[CUSTOMER_MAIL vs PRACTICE_HUB] | 0.039347 | 0.012951 | 3.0381 | 0.00238102 | [0.013963, 0.064731] | Yes |
| PRESCRIPTION_SOURCE[CVC vs PRACTICE_HUB] | -0.001359 | 0.053011 | -0.0256 | 0.979547 | [-0.105259, 0.102541] | No |
| PRESCRIPTION_SOURCE[DIGITAL vs PRACTICE_HUB] | 0.041389 | 0.040514 | 1.0216 | 0.306972 | [-0.038017, 0.120795] | No |
| PRESCRIPTION_SOURCE[FAX vs PRACTICE_HUB] | -0.006481 | 0.011356 | -0.5707 | 0.56821 | [-0.028738, 0.015777] | No |
| PRESCRIPTION_SOURCE[PARTNER_API vs PRACTICE_HUB] | 0.021957 | 0.007964 | 2.7572 | 0.00583076 | [0.006349, 0.037566] | Yes |
| PRESCRIPTION_SOURCE[RHAPSODY vs PRACTICE_HUB] | -0.070004 | 0.063178 | -1.1081 | 0.267837 | [-0.193830, 0.053821] | No |
| PRESCRIPTION_SOURCE[TELEMEDICINE vs PRACTICE_HUB] | 0.140373 | 0.053399 | 2.6288 | 0.00856957 | [0.035713, 0.245034] | Yes |
| PRESCRIPTION_SOURCE[VERBAL vs PRACTICE_HUB] | 0.000359 | 0.011928 | 0.0301 | 0.975999 | [-0.023019, 0.023737] | No |

## Variance

| Component | SD | Approximate 95% CI |
|---|---:|---:|
| Residual | 0.592008 | [0.591557, 0.592461] |

## Interpretation and assumptions

The `SAME_PRECEDING` estimate is an adjusted observational association, not a
causal effect. It assumes additive fixed effects and independent normally
distributed residuals with a common variance on the Box-Cox scale. The
`SAME_FOLLOWING` placebo can reveal sequence-related confounding but cannot
establish causal identification. The paired t-test is
also observational; neither analysis identifies a causal effect. Their
estimates are not directly comparable because the task populations and
preceding-task rules differ. Here same cohort means a valid-DUR cohort batch;
the paired test uses the previous task of the day.

## Diagnostics and artifacts

The residual Q–Q plot curves in both tails. Normal-based confidence intervals
should therefore be read as model-based approximations. The
predicted-versus-observed plot shows broad spread around the diagonal.

![Conditional residual Q–Q plot](../../charts/cohort-user-date-model/conditional_residuals_qq.png)

![Predicted versus outcome](../../charts/cohort-user-date-model/predicted_vs_boxcox_actual.png)

- [Generated SQL](../../../generated/cohort_user_date_model.sql)
- [Raw task data](../../../data/cohort_user_date_model_task_data.parquet)
- [Transformed model data](../../../data/cohort_user_date_model_boxcox_data.parquet)
- [Fixed-effect table](../../tables/cohort_user_date_model_fixed_effects.md)
