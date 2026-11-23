-- Platform weekly rates: crude vs constant mix vs stable cohort (SIMULATED).
SELECT week_start, control_events, fp_rate_crude, fp_rate_standardized, fp_rate_stable_cohort,
       fn_rate_crude, fn_rate_standardized, fn_rate_stable_cohort
FROM mart_mix_standardized
