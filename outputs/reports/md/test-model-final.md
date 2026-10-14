# test-model-final

This model keeps the natural log outcome, no-cell specification, fixed effects,
and user/date random intercepts of [test-model-exp](test-model-exp.md).
It changes the sequence indicators from cohort-and-pet batches to cohort-only
batches.

## Sample and indicators

The source is `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS` through the
[cohort-only extract](../../../data/cohort_user_date_model_task_data.parquet). The strict global
P95 filter retains 3,433,218 positive-duration tasks. For within-batch task
position $S_i=$ `COHORT_SEQN` and batch length $L_i=$
`COHORT_BATCH_LEN`, `SAME_PRECEDING` is
$P_i=\mathbf{1}(L_i>1\land S_i>1)$ and `SAME_FOLLOWING` is
$F_i=\mathbf{1}(L_i>1\land S_i<L_i)$. `HAS_CORRECTION` is
$C_i=\mathbf{1}(N_i>0)$ for correction count $N_i$.

| Indicator | Value | Tasks | Percent of retained tasks |
|---|---:|---:|---:|
| SAME_PRECEDING | 0 | 1,875,931 | 54.64% |
| SAME_PRECEDING | 1 | 1,557,287 | 45.36% |
| SAME_FOLLOWING | 0 | 1,878,842 | 54.73% |
| SAME_FOLLOWING | 1 | 1,554,376 | 45.27% |

## Model formula

With cohort $c_i$, pet type $p_i$, weekday $w_i$, approval channel $a_i$,
prescription source $s_i$, user $u(i)$, and date $d(i)$:

$$
\log(Y_i)=\alpha+\beta_P P_i+\beta_F F_i+\beta_C C_i
 +\gamma_{c_i}+\delta_{p_i}+\theta_{w_i}
 +\phi_{a_i}+\psi_{s_i}+b_{u(i)}+h_{d(i)}+\epsilon_i.
$$

There are no fixed cells. Cohort, pet type, weekday, approval channel, and
prescription source are additive fixed effects. Their reference levels are
`Cohort 1`, `Dog`, Sunday,
`PH`, and
`PRACTICE_HUB`, respectively. User and date are
independent random intercepts: $b_u\sim N(0,\sigma_u^2)$ and
$h_d\sim N(0,\sigma_d^2)$, independently of
$\epsilon_i\sim N(0,\sigma_e^2)$. REML estimates the model. Fixed-effect
intervals and p-values use normal Wald approximations; random SD intervals
use observed information on the log-SD scale, and the residual SD interval
uses a chi-square approximation. The global intercept
$\widehat{\alpha}=2.919039$ applies to reference categories, zero
indicator values, and zero random intercepts.

## Sample and fit

| Quantity | Value |
|---|---:|
| Tasks | 3,433,218 |
| Fixed cells | 0 |
| Global intercept (log seconds) | 2.919039 |
| Users | 340 |
| Dates | 182 |
| Global approximate P95 cutoff (seconds) | 156.562717 |
| Conditional R-squared (log scale) | 0.288292 |
| Conditional RMSE (log seconds) | 0.774296 |
| REML negative log-likelihood | 3995433.888632 |
| Converged | True |

## Fixed effects

| Term | Estimate | SE | z | p-value | 95% CI | Significant |
|---|---:|---:|---:|---:|---:|:---:|
| SAME_PRECEDING | -0.037134 | 0.000865 | -42.9444 | <1e-300 | [-0.038828, -0.035439] | Yes |
| SAME_FOLLOWING | -0.003052 | 0.000865 | -3.5300 | 0.000415624 | [-0.004747, -0.001358] | Yes |
| HAS_CORRECTION | 0.351859 | 0.001004 | 350.3831 | <1e-300 | [0.349891, 0.353827] | Yes |
| WEEKDAY_MON | 0.008581 | 0.025262 | 0.3397 | 0.734102 | [-0.040932, 0.058094] | No |
| WEEKDAY_TUE | 0.019428 | 0.025258 | 0.7692 | 0.441791 | [-0.030077, 0.068933] | No |
| WEEKDAY_WED | 0.015688 | 0.025264 | 0.6210 | 0.53463 | [-0.033829, 0.065204] | No |
| WEEKDAY_THU | 0.013033 | 0.025266 | 0.5158 | 0.60597 | [-0.036488, 0.062554] | No |
| WEEKDAY_FRI | 0.009690 | 0.025265 | 0.3835 | 0.701312 | [-0.039828, 0.059208] | No |
| WEEKDAY_SAT | 0.004731 | 0.025284 | 0.1871 | 0.851583 | [-0.044825, 0.054286] | No |
| COH[Cohort 2 vs Cohort 1] | 0.208605 | 0.000906 | 230.2063 | <1e-300 | [0.206829, 0.210381] | Yes |
| COH[Cohort 3 vs Cohort 1] | 0.554847 | 0.002160 | 256.8827 | <1e-300 | [0.550613, 0.559080] | Yes |
| COH[Cohort 4 vs Cohort 1] | 0.922623 | 0.005945 | 155.2017 | <1e-300 | [0.910971, 0.934274] | Yes |
| COH[Unknown vs Cohort 1] | 0.758075 | 0.005442 | 139.3116 | <1e-300 | [0.747410, 0.768741] | Yes |
| PETTYPE[<Missing> vs Dog] | -0.830892 | 0.547585 | -1.5174 | 0.129172 | [-1.904138, 0.242354] | No |
| PETTYPE[Bird vs Dog] | 0.566695 | 0.031627 | 17.9182 | 8.50243e-72 | [0.504708, 0.628683] | Yes |
| PETTYPE[Cat vs Dog] | 0.132653 | 0.001289 | 102.8821 | <1e-300 | [0.130126, 0.135180] | Yes |
| PETTYPE[Farm Animal vs Dog] | 0.533847 | 0.193705 | 2.7560 | 0.00585178 | [0.154191, 0.913503] | Yes |
| PETTYPE[Fish vs Dog] | 0.666540 | 0.143804 | 4.6351 | 3.5685e-06 | [0.384689, 0.948392] | Yes |
| PETTYPE[Horse vs Dog] | -0.083708 | 0.003673 | -22.7878 | 6.05573e-115 | [-0.090908, -0.076508] | Yes |
| PETTYPE[Reptile vs Dog] | 0.322245 | 0.050742 | 6.3506 | 2.14443e-10 | [0.222792, 0.421698] | Yes |
| PETTYPE[Small Pet vs Dog] | 0.478073 | 0.011900 | 40.1759 | <1e-300 | [0.454751, 0.501396] | Yes |
| APPROVAL_CHANNEL[CLINIC_EMAIL vs PH] | 0.325924 | 0.057970 | 5.6223 | 1.88443e-08 | [0.212305, 0.439544] | Yes |
| APPROVAL_CHANNEL[CUSTOMER_MAIL vs PH] | 0.611744 | 0.016746 | 36.5315 | 3.50285e-292 | [0.578924, 0.644565] | Yes |
| APPROVAL_CHANNEL[DIGITAL vs PH] | 0.200442 | 0.052223 | 3.8382 | 0.000123939 | [0.098087, 0.302797] | Yes |
| APPROVAL_CHANNEL[FAX vs PH] | 0.265223 | 0.014394 | 18.4257 | 8.16859e-76 | [0.237011, 0.293435] | Yes |
| APPROVAL_CHANNEL[PARTNER vs PH] | -0.050762 | 0.010196 | -4.9785 | 6.40774e-07 | [-0.070747, -0.030778] | Yes |
| APPROVAL_CHANNEL[RHAPSODY vs PH] | 0.132077 | 0.067399 | 1.9596 | 0.0500387 | [-0.000022, 0.264177] | No |
| APPROVAL_CHANNEL[VERBAL vs PH] | -0.000181 | 0.013672 | -0.0132 | 0.989433 | [-0.026978, 0.026616] | No |
| APPROVAL_CHANNEL[VET vs PH] | 0.027155 | 0.135566 | 0.2003 | 0.841237 | [-0.238549, 0.292860] | No |
| PRESCRIPTION_SOURCE[CLINIC_EMAIL vs PRACTICE_HUB] | -0.013493 | 0.014335 | -0.9413 | 0.346558 | [-0.041589, 0.014602] | No |
| PRESCRIPTION_SOURCE[CS_FIRST_CONTACT vs PRACTICE_HUB] | -0.149065 | 0.261454 | -0.5701 | 0.568583 | [-0.661505, 0.363374] | No |
| PRESCRIPTION_SOURCE[CUSTOMER_MAIL vs PRACTICE_HUB] | 0.040621 | 0.016427 | 2.4728 | 0.0134047 | [0.008425, 0.072816] | Yes |
| PRESCRIPTION_SOURCE[CVC vs PRACTICE_HUB] | 0.000098 | 0.067319 | 0.0015 | 0.998842 | [-0.131846, 0.132041] | No |
| PRESCRIPTION_SOURCE[DIGITAL vs PRACTICE_HUB] | 0.022401 | 0.051424 | 0.4356 | 0.663112 | [-0.078388, 0.123191] | No |
| PRESCRIPTION_SOURCE[FAX vs PRACTICE_HUB] | -0.017322 | 0.014390 | -1.2037 | 0.228704 | [-0.045526, 0.010883] | No |
| PRESCRIPTION_SOURCE[PARTNER_API vs PRACTICE_HUB] | 0.033038 | 0.010154 | 3.2537 | 0.00113914 | [0.013136, 0.052939] | Yes |
| PRESCRIPTION_SOURCE[RHAPSODY vs PRACTICE_HUB] | -0.083006 | 0.080429 | -1.0320 | 0.302054 | [-0.240644, 0.074632] | No |
| PRESCRIPTION_SOURCE[TELEMEDICINE vs PRACTICE_HUB] | 0.174528 | 0.067831 | 2.5730 | 0.0100831 | [0.041581, 0.307475] | Yes |
| PRESCRIPTION_SOURCE[VERBAL vs PRACTICE_HUB] | -0.007858 | 0.015045 | -0.5223 | 0.601451 | [-0.037345, 0.021629] | No |

The `SAME_PRECEDING` estimate corresponds to an adjusted duration ratio of
$\exp(\widehat{\beta}_P)=0.963547$, or
-3.65% (95% CI [-3.81%, -3.48%]).
This is a conditional log-scale association, not a causal effect.

## Variance components

| Component | SD (log scale) | Approximate 95% CI |
|---|---:|---:|
| User random intercept | 0.542655 | [0.501625, 0.587041] |
| Date random intercept | 0.090785 | [0.081698, 0.100882] |
| Residual | 0.774357 | [0.773779, 0.774937] |

## Interpretation and assumptions

The model assumes additive effects, independent normally distributed user
and date intercepts and residuals, and a common log-scale residual variance.
Unmodeled user and date differences must be unrelated to the included
predictors after adjustment for the random-intercept interpretation. This
remains an observational association. It is not directly comparable to the
paired t-test, which uses a different task population and preceding-task rule.
Coefficients and fit measures on the log scale are not directly comparable to
those on the Box-Cox scale in `test-model`. This model and `test-model-exp`
also estimate different sequence associations because their preceding and
following indicators use different batch definitions.

## Diagnostics and artifacts

The date random-intercept Q–Q plot departs strongly from a normal line, and
the date intercept density shows a second positive peak. The residual Q–Q
plot curves in both tails. The reported confidence intervals are model-based
approximations under the stated distributional assumptions.

![User random-intercept Q–Q plot](../../charts/test-model-final/user_random_intercepts_qq.png)

![Date random-intercept Q–Q plot](../../charts/test-model-final/date_random_intercepts_qq.png)

Each density plot gives one fitted intercept equal weight per user or date;
the dashed vertical line marks zero.

![User random-intercept density](../../charts/tes1t-model-final/user_random_intercepts_density.png)

![Date random-intercept density](../../charts/test-model-final/date_random_intercepts_density.png)

![Conditional residual Q–Q plot](../../charts/test-model-final/conditional_residuals_qq.png)

![Predicted versus outcome](../../charts/test-model-final/predicted_vs_log_actual.png)

- [Shared generated SQL](../../../generated/cohort_user_date_model.sql)
- [Shared raw task data](../../../data/cohort_user_date_model_task_data.parquet)
- [Log-transformed model data](../../../data/test_model_final_log_data.parquet)
- [Fixed-effect table](../../tables/test_model_final_fixed_effects.md)
- [User-effect table](../../tables/test_model_final_user_effects.md)
- [Date-effect table](../../tables/test_model_final_date_effects.md)
- [User-effect data](../../../data/test_model_final_user_effects.parquet)
- [Date-effect data](../../../data/test_model_final_date_effects.parquet)
