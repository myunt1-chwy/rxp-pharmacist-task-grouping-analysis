# cohort_user_date_pettype_cell_model

Fixed `(COH, PETTYPE, D)` cells with a `USER_ID` random intercept.

## Sample and indicators

This model uses the valid-DUR table and global strict P95 filter as the
[cohort/pet-type/user/date fixed-cell model](cohort_user_date_model.md).
The source is `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS`. The raw cache contains positive imputed
DUR durations and valid `COHORT_PET_SEQN` and `COHORT_PET_BATCH_LEN` values. The
cohort-and-pet batches follow the valid-DUR pipeline's consecutive-task and
one-hour-break rules, and restart when the cohort or pet type changes.
`COHORT_PET_SEQN` is the task position within a batch; the pipeline's
`COHORT_PET_BATCH_SEQN` is an intermediate batch identifier and is not an
output column of the valid-DUR table.
Missing cohort, pet type, approval channel, and prescription source are
represented by `<Missing>`.

For cohort sequence number $S_i$, batch length $L_i$, and correction count
$N_i$, the model includes `SAME_PRECEDING`
$P_i=\mathbf{1}(L_i>1\land S_i>1)$, the `SAME_FOLLOWING` placebo
$F_i=\mathbf{1}(L_i>1\land S_i<L_i)$, and `HAS_CORRECTION`
$C_i=\mathbf{1}(N_i>0)$. One global Box-Cox transform of retained duration
$Y_i$ gives $Z_i=g_\lambda(Y_i)$, with
$\widehat{\lambda}=-0.08159843$.

The indicators have the following distribution among the 3,433,218 tasks
retained after the global P95 filter. Percentages use all retained tasks as
the denominator. `SAME_PRECEDING` applies to 126,838 tasks
(3.69%), `SAME_FOLLOWING` to 125,123
(3.64%), and both indicators to 5,092
(0.15%).

| Indicator | Value | Tasks | Percent |
|---|---:|---:|---:|
| SAME_PRECEDING | 0 | 3,306,380 | 96.31% |
| SAME_PRECEDING | 1 | 126,838 | 3.69% |
| SAME_FOLLOWING | 0 | 3,308,095 | 96.36% |
| SAME_FOLLOWING | 1 | 125,123 | 3.64% |

Their joint distribution shows how often both indicators apply to a task:

| SAME_PRECEDING | SAME_FOLLOWING | Tasks | Percent |
|---:|---:|---:|---:|
| 0 | 0 | 3,186,349 | 92.81% |
| 0 | 1 | 120,031 | 3.50% |
| 1 | 0 | 121,746 | 3.55% |
| 1 | 1 | 5,092 | 0.15% |

Among the 2,841 observed `(COH, PETTYPE, D)` cells,
1,045 (36.78%) contain at least two
tasks with `SAME_PRECEDING = 1` and at least two with `SAME_PRECEDING = 0`
in the retained sample.

## Model formula

Let $c(i)=(\mathrm{COH}_i,\mathrm{PETTYPE}_i,D_i)$ be the fixed cell,
$u(i)$ the user, $A_i$ the approval channel, and $R_i$ the prescription source:

$$
\begin{aligned}
Z_i={}&\gamma_{c(i)}+\beta_P P_i+\beta_F F_i+\beta_C C_i\\
&+\sum_{a\ne a_0}\theta_a\mathbf{1}(A_i=a)
 +\sum_{s\ne s_0}\phi_s\mathbf{1}(R_i=s)\\
&+b_{u(i)}+\epsilon_i.
\end{aligned}
$$

There is one fixed effect per observed `(COH, PETTYPE, D)` cell and no overall
intercept. Date in the cell absorbs weekday, so no weekday contrast is fitted.
User is the only random intercept:
$b_u\sim N(0,\sigma_u^2)$ and independently
$\epsilon_i\sim N(0,\sigma_e^2)$. The reference approval channel is
`PH` and the reference prescription source
is `PRACTICE_HUB` (the most frequent levels, with
lexicographic tie breaking). REML estimates the fixed effects and variance
components. Fixed-effect intervals and p-values use normal Wald approximations;
the user SD interval uses observed information on the log-SD scale, and the
residual SD interval uses a chi-square approximation. All results are on the
Box-Cox scale.

## Sample and fit

| Quantity | Value |
|---|---:|
| Tasks | 3,433,218 |
| Cohort/pet-type/date cells | 2,841 |
| Users | 340 |
| Dates | 182 |
| Global approximate P95 cutoff (seconds) | 156.487990 |
| Box-Cox lambda | -0.08159843 |
| Conditional R-squared | 0.298174 |
| Conditional RMSE | 0.608290 |
| REML negative log-likelihood | 3170866.330418 |
| Converged | True |

## Fixed effects

| Term | Estimate | SE | z | p-value | 95% CI | Significant |
|---|---:|---:|---:|---:|---:|:---:|
| SAME_PRECEDING | -0.134601 | 0.001751 | -76.8849 | <1e-300 | [-0.138032, -0.131169] | Yes |
| SAME_FOLLOWING | 0.002054 | 0.001762 | 1.1660 | 0.243633 | [-0.001399, 0.005508] | No |
| HAS_CORRECTION | 0.283382 | 0.000790 | 358.6249 | <1e-300 | [0.281834, 0.284931] | Yes |
| APPROVAL_CHANNEL[CLINIC_EMAIL vs PH] | 0.253155 | 0.045573 | 5.5549 | 2.77789e-08 | [0.163833, 0.342477] | Yes |
| APPROVAL_CHANNEL[CUSTOMER_MAIL vs PH] | 0.481983 | 0.013168 | 36.6017 | 2.68707e-293 | [0.456174, 0.507793] | Yes |
| APPROVAL_CHANNEL[DIGITAL vs PH] | 0.158492 | 0.041052 | 3.8608 | 0.00011302 | [0.078032, 0.238952] | Yes |
| APPROVAL_CHANNEL[FAX vs PH] | 0.213192 | 0.011320 | 18.8338 | 3.99034e-79 | [0.191006, 0.235378] | Yes |
| APPROVAL_CHANNEL[PARTNER vs PH] | -0.047035 | 0.008019 | -5.8653 | 4.48408e-09 | [-0.062753, -0.031318] | Yes |
| APPROVAL_CHANNEL[RHAPSODY vs PH] | 0.105324 | 0.052987 | 1.9877 | 0.0468399 | [0.001472, 0.209176] | Yes |
| APPROVAL_CHANNEL[VERBAL vs PH] | 0.000052 | 0.010752 | 0.0048 | 0.99616 | [-0.021022, 0.021125] | No |
| APPROVAL_CHANNEL[VET vs PH] | 0.017090 | 0.106563 | 0.1604 | 0.872588 | [-0.191770, 0.225950] | No |
| PRESCRIPTION_SOURCE[CLINIC_EMAIL vs PRACTICE_HUB] | -0.011845 | 0.011273 | -1.0507 | 0.293394 | [-0.033939, 0.010250] | No |
| PRESCRIPTION_SOURCE[CS_FIRST_CONTACT vs PRACTICE_HUB] | -0.098574 | 0.205590 | -0.4795 | 0.631604 | [-0.501522, 0.304374] | No |
| PRESCRIPTION_SOURCE[CUSTOMER_MAIL vs PRACTICE_HUB] | 0.032253 | 0.012918 | 2.4968 | 0.0125315 | [0.006935, 0.057571] | Yes |
| PRESCRIPTION_SOURCE[CVC vs PRACTICE_HUB] | -0.000881 | 0.052924 | -0.0166 | 0.986723 | [-0.104610, 0.102849] | No |
| PRESCRIPTION_SOURCE[DIGITAL vs PRACTICE_HUB] | 0.022187 | 0.040429 | 0.5488 | 0.583153 | [-0.057053, 0.101427] | No |
| PRESCRIPTION_SOURCE[FAX vs PRACTICE_HUB] | -0.013589 | 0.011316 | -1.2008 | 0.229826 | [-0.035769, 0.008591] | No |
| PRESCRIPTION_SOURCE[PARTNER_API vs PRACTICE_HUB] | 0.033512 | 0.007989 | 4.1950 | 2.72872e-05 | [0.017855, 0.049170] | Yes |
| PRESCRIPTION_SOURCE[RHAPSODY vs PRACTICE_HUB] | -0.064536 | 0.063228 | -1.0207 | 0.307401 | [-0.188461, 0.059388] | No |
| PRESCRIPTION_SOURCE[TELEMEDICINE vs PRACTICE_HUB] | 0.143958 | 0.053327 | 2.6995 | 0.00694364 | [0.039439, 0.248477] | Yes |
| PRESCRIPTION_SOURCE[VERBAL vs PRACTICE_HUB] | -0.008142 | 0.011840 | -0.6876 | 0.491679 | [-0.031348, 0.015064] | No |

## Variance components

| Component | SD | Approximate 95% CI |
|---|---:|---:|
| User random intercept | 0.420534 | [0.388806, 0.454851] |
| Residual | 0.608573 | [0.608118, 0.609028] |

## Interpretation and assumptions

`SAME_PRECEDING` is an adjusted observational association. Neither this model
nor the paired t-test identifies a causal effect. The model assumes additive
fixed effects, normally distributed independent user intercepts and residuals,
and a common residual variance on the Box-Cox scale. The user random-effect
assumption also requires users' unmodeled duration differences to be unrelated
to the included predictors after adjustment. The `SAME_FOLLOWING` placebo can
indicate sequence-related confounding. Compared with the fixed-user model,
this variant replaces user-specific cell intercepts with a shared random user
intercept; its coefficient need not have the same interpretation. The paired
t-test uses a different task population and preceding-task rule.

## Diagnostics and artifacts

![User random-intercept Q–Q plot](../../charts/cohort-user-date-pettype-cell-model/user_random_intercepts_qq.png)

![Conditional residual Q–Q plot](../../charts/cohort-user-date-pettype-cell-model/conditional_residuals_qq.png)

![Predicted versus outcome](../../charts/cohort-user-date-pettype-cell-model/predicted_vs_boxcox_actual.png)

- [Generated SQL](../../../generated/cohort_user_date_pettype_cell_model.sql)
- [Raw task data](../../../data/cohort_user_date_pettype_cell_model_task_data.parquet)
- [Fixed-effect table](../../tables/cohort_user_date_pettype_cell_model_fixed_effects.md)
- [User-effect table](../../tables/cohort_user_date_pettype_cell_model_user_effects.md)
- [User-effect data](../../../data/cohort_user_date_pettype_cell_model_user_effects.parquet)
