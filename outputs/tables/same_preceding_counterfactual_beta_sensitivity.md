# Same-preceding coefficient sensitivity

The same 1,814,117 eligible tasks are adjusted in each scenario. For each
task, the original duration is multiplied by `exp(beta_P)`; all other tasks
retain their original durations. Implied labor value is the resulting saved
seconds divided by 3,600 and multiplied by $90 per hour. Coefficients use the
fitted estimate and exact 95% confidence bounds from `test-model-final`.
The task-created date filter is 2026-02-01 inclusive through 2026-08-01
exclusive, or 181 days. Annualized values multiply the unrounded period labor
value by 365/181 and assume constant average daily task volume and mix. The
retained process-date range extends to August 1 because of spillover; its
182-date inclusive span does not add a full source day.

| Coefficient scenario | beta_P | 181-day implied labor value | Annualized 365-day value |
|---|---:|---:|---:|
| Lower 95% bound | -0.036552403351 | $43,793.22 | $88,312.30 |
| Fitted estimate | -0.034870727493 | $41,813.35 | $84,319.74 |
| Upper 95% bound | -0.033189051635 | $39,830.15 | $80,320.46 |

These values vary only the fitted coefficient; they are not a confidence
interval for realizable cash savings.
