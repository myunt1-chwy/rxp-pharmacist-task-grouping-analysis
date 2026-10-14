# test-model-exp

This model has no fixed cells. It uses the same sample and covariates as
[test-model](test-model.md), with natural log duration as the
outcome instead of the fitted Box-Cox transformation.

## Sample and indicators

The source is `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS` through the
[shared cohort-and-pet extract](../../../data/cohort_user_date_pettype_cell_model_task_data.parquet). The strict global
P95 filter retains 3,433,218 positive-duration tasks. `SAME_PRECEDING` and
`SAME_FOLLOWING` retain the cohort-and-pet definitions: for within-batch task
position $S_i=$ `COHORT_PET_SEQN` and batch length $L_i=$
`COHORT_PET_BATCH_LEN`, $P_i=\mathbf{1}(L_i>1\land S_i>1)$ and
$F_i=\mathbf{1}(L_i>1\land S_i<L_i)$. `HAS_CORRECTION` is
$C_i=\mathbf{1}(N_i>0)$ for correction count $N_i$.

| Indicator | Value | Tasks | Percent of retained tasks |
|---|---:|---:|---:|
| SAME_PRECEDING | 0 | 3,306,380 | 96.31% |
| SAME_PRECEDING | 1 | 126,838 | 3.69% |
| SAME_FOLLOWING | 0 | 3,308,095 | 96.36% |
| SAME_FOLLOWING | 1 | 125,123 | 3.64% |

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
$\widehat{\alpha}=2.904094$ applies to reference categories, zero
indicator values, and zero random intercepts.

## Sample and fit

| Quantity | Value |
|---|---:|
| Tasks | 3,433,218 |
| Fixed cells | 0 |
| Global intercept (log seconds) | 2.904094 |
| Users | 340 |
| Dates | 182 |
| Global approximate P95 cutoff (seconds) | 156.487990 |
| Conditional R-squared (log scale) | 0.289134 |
| Conditional RMSE (log seconds) | 0.773837 |
| REML negative log-likelihood | 3993395.204100 |
| Converged | True |

## Fixed effects

| Term | Estimate | SE | z | p-value | 95% CI | Significant |
|---|---:|---:|---:|---:|---:|:---:|
| SAME_PRECEDING | -0.171335 | 0.002224 | -77.0534 | <1e-300 | [-0.175693, -0.166977] | Yes |
| SAME_FOLLOWING | 0.000389 | 0.002238 | 0.1738 | 0.862048 | [-0.003998, 0.004775] | No |
| HAS_CORRECTION | 0.351896 | 0.001004 | 350.6303 | <1e-300 | [0.349928, 0.353863] | Yes |
| WEEKDAY_MON | 0.008431 | 0.024685 | 0.3415 | 0.732704 | [-0.039951, 0.056813] | No |
| WEEKDAY_TUE | 0.019426 | 0.024681 | 0.7871 | 0.431228 | [-0.028948, 0.067800] | No |
| WEEKDAY_WED | 0.015887 | 0.024687 | 0.6436 | 0.519862 | [-0.032498, 0.064273] | No |
| WEEKDAY_THU | 0.013158 | 0.024689 | 0.5330 | 0.594065 | [-0.035232, 0.061548] | No |
| WEEKDAY_FRI | 0.010038 | 0.024688 | 0.4066 | 0.684295 | [-0.038349, 0.058425] | No |
| WEEKDAY_SAT | 0.005062 | 0.024707 | 0.2049 | 0.837674 | [-0.043364, 0.053487] | No |
| COH[Cohort 2 vs Cohort 1] | 0.215003 | 0.000888 | 242.0472 | <1e-300 | [0.213262, 0.216744] | Yes |
| COH[Cohort 3 vs Cohort 1] | 0.569687 | 0.002087 | 272.9845 | <1e-300 | [0.565597, 0.573777] | Yes |
| COH[Cohort 4 vs Cohort 1] | 0.933650 | 0.005914 | 157.8598 | <1e-300 | [0.922058, 0.945242] | Yes |
| COH[Unknown vs Cohort 1] | 0.770221 | 0.005408 | 142.4262 | <1e-300 | [0.759622, 0.780821] | Yes |
| PETTYPE[<Missing> vs Dog] | -0.840443 | 0.547260 | -1.5357 | 0.124605 | [-1.913053, 0.232168] | No |
| PETTYPE[Bird vs Dog] | 0.565913 | 0.031608 | 17.9041 | 1.09597e-71 | [0.503963, 0.627864] | Yes |
| PETTYPE[Cat vs Dog] | 0.130059 | 0.001290 | 100.8568 | <1e-300 | [0.127531, 0.132586] | Yes |
| PETTYPE[Farm Animal vs Dog] | 0.529816 | 0.193591 | 2.7368 | 0.00620435 | [0.150385, 0.909247] | Yes |
| PETTYPE[Fish vs Dog] | 0.672260 | 0.143719 | 4.6776 | 2.90258e-06 | [0.390576, 0.953945] | Yes |
| PETTYPE[Horse vs Dog] | -0.086304 | 0.003672 | -23.5060 | 3.54524e-122 | [-0.093500, -0.079107] | Yes |
| PETTYPE[Reptile vs Dog] | 0.319034 | 0.050712 | 6.2911 | 3.15303e-10 | [0.219640, 0.418428] | Yes |
| PETTYPE[Small Pet vs Dog] | 0.476451 | 0.011893 | 40.0631 | <1e-300 | [0.453142, 0.499760] | Yes |
| APPROVAL_CHANNEL[CLINIC_EMAIL vs PH] | 0.323645 | 0.057936 | 5.5863 | 2.31993e-08 | [0.210093, 0.437197] | Yes |
| APPROVAL_CHANNEL[CUSTOMER_MAIL vs PH] | 0.613457 | 0.016736 | 36.6554 | 3.74881e-294 | [0.580655, 0.646258] | Yes |
| APPROVAL_CHANNEL[DIGITAL vs PH] | 0.202293 | 0.052192 | 3.8759 | 0.00010621 | [0.099999, 0.304588] | Yes |
| APPROVAL_CHANNEL[FAX vs PH] | 0.263797 | 0.014386 | 18.3375 | 4.15707e-75 | [0.235602, 0.291992] | Yes |
| APPROVAL_CHANNEL[PARTNER vs PH] | -0.056129 | 0.010191 | -5.5077 | 3.63494e-08 | [-0.076102, -0.036155] | Yes |
| APPROVAL_CHANNEL[RHAPSODY vs PH] | 0.136987 | 0.067359 | 2.0337 | 0.041984 | [0.004965, 0.269008] | Yes |
| APPROVAL_CHANNEL[VERBAL vs PH] | -0.000802 | 0.013664 | -0.0587 | 0.953186 | [-0.027584, 0.025979] | No |
| APPROVAL_CHANNEL[VET vs PH] | 0.025639 | 0.135486 | 0.1892 | 0.849905 | [-0.239908, 0.291186] | No |
| PRESCRIPTION_SOURCE[CLINIC_EMAIL vs PRACTICE_HUB] | -0.014385 | 0.014326 | -1.0041 | 0.315328 | [-0.042464, 0.013694] | No |
| PRESCRIPTION_SOURCE[CS_FIRST_CONTACT vs PRACTICE_HUB] | -0.123679 | 0.261299 | -0.4733 | 0.635982 | [-0.635815, 0.388457] | No |
| PRESCRIPTION_SOURCE[CUSTOMER_MAIL vs PRACTICE_HUB] | 0.039186 | 0.016417 | 2.3869 | 0.0169894 | [0.007010, 0.071363] | Yes |
| PRESCRIPTION_SOURCE[CVC vs PRACTICE_HUB] | -0.006624 | 0.067280 | -0.0985 | 0.921571 | [-0.138489, 0.125241] | No |
| PRESCRIPTION_SOURCE[DIGITAL vs PRACTICE_HUB] | 0.027091 | 0.051394 | 0.5271 | 0.598112 | [-0.073639, 0.127820] | No |
| PRESCRIPTION_SOURCE[FAX vs PRACTICE_HUB] | -0.017157 | 0.014382 | -1.1930 | 0.232888 | [-0.045344, 0.011031] | No |
| PRESCRIPTION_SOURCE[PARTNER_API vs PRACTICE_HUB] | 0.040578 | 0.010149 | 3.9982 | 6.38192e-05 | [0.020686, 0.060470] | Yes |
| PRESCRIPTION_SOURCE[RHAPSODY vs PRACTICE_HUB] | -0.086266 | 0.080382 | -1.0732 | 0.283178 | [-0.243811, 0.071279] | No |
| PRESCRIPTION_SOURCE[TELEMEDICINE vs PRACTICE_HUB] | 0.175940 | 0.067791 | 2.5953 | 0.00945039 | [0.043071, 0.308808] | Yes |
| PRESCRIPTION_SOURCE[VERBAL vs PRACTICE_HUB] | -0.010773 | 0.015036 | -0.7165 | 0.473707 | [-0.040243, 0.018697] | No |

The `SAME_PRECEDING` estimate corresponds to an adjusted duration ratio of
$\exp(\widehat{\beta}_P)=0.842539$, or
-15.75% (95% CI [-16.11%, -15.38%]).
This is a conditional log-scale association, not a causal effect.

## Variance components

| Component | SD (log scale) | Approximate 95% CI |
|---|---:|---:|
| User random intercept | 0.542884 | [0.501838, 0.587286] |
| Date random intercept | 0.088697 | [0.079813, 0.098570] |
| Residual | 0.773899 | [0.773320, 0.774478] |

## Interpretation and assumptions

The model assumes additive effects, independent normally distributed user
and date intercepts and residuals, and a common log-scale residual variance.
Unmodeled user and date differences must be unrelated to the included
predictors after adjustment for the random-intercept interpretation. This
remains an observational association. It is not directly comparable to the
paired t-test, which uses a different task population and preceding-task rule.
Coefficients and fit measures on the log scale are not directly comparable to
those on the Box-Cox scale in `test-model`.

## Diagnostics and artifacts

The date random-intercept Q–Q plot departs strongly from a normal line, and
the residual Q–Q plot curves in both tails. The reported confidence intervals
are model-based approximations under the stated distributional assumptions.

![User random-intercept Q–Qplot](../../charts/test-model-exp/user_random_intercepts_qq.png)

![Date random-intercept Q–Q plot](../../charts/test-model-exp/date_random_intercepts_qq.png)

![Conditional residual Q–Q plot](../../charts/test-model-exp/conditional_residuals_qq.png)

![Predicted versus outcome](../../charts/test-model-exp/predicted_vs_log_actual.png)

- [Shared generated SQL](../../../generated/cohort_user_date_pettype_cell_model.sql)
- [Shared raw task data](../../../data/cohort_user_date_pettype_cell_model_task_data.parquet)
- [Log-transformed model data](../../../data/test_model_exp_log_data.parquet)
- [Fixed-effect table](../../tables/test_model_exp_fixed_effects.md)
- [User-effect table](../../tables/test_model_exp_user_effects.md)
- [Date-effect table](../../tables/test_model_exp_date_effects.md)
- [User-effect data](../../../data/test_model_exp_user_effects.parquet)
- [Date-effect data](../../../data/test_model_exp_date_effects.parquet)
