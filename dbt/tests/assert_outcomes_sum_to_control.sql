-- Accounting identity of the accuracy experiment: every control event gets exactly one outcome.
--   TP + FP + FN + TN = control events (bad robots excluded on both sides)
select event_date, customer_id, browser, browser_major, device_type, control_events, tp + fp + fn + tn as outcomes
from {{ ref('fct_accuracy_daily') }}
where tp + fp + fn + tn <> control_events
