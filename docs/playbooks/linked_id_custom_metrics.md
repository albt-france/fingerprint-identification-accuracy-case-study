# Playbook: customer-specific metrics from account ids (linkedId)

**Trigger**: standard metrics do not answer the customer's question, typically "one visitor id groups many of my
accounts" or "one account has many visitor ids". The customer sends its own account id with each request (`linkedId`,
see [Fingerprint docs: identify visitors](https://docs.fingerprint.com/docs/identify-visitors)).

## How I approached it (C07, SIMULATED) in 6 steps

1. **Rephrase the question as a metric**: "accounts per visitor id" (distinct accounts seen with one visitor) and its
   tail (99th percentile, share of visitors with more than 5 accounts). Agree with the CSM that this is what C07 means.
2. **Reproduce their number** from their export (`C07_accounts_export.csv`) and from our pairs table
   (`int_linked_id_pairs`): same pairs, same counts. Only then interpret.
3. **Look at the extreme visitors first**: the top visitor ids had thousands of accounts. No identification error links
   thousands of people; that pattern means **one device used by staff**.
4. **Characterise them without truth**: 20+ accounts and a network shared by 5+ such visitors, mostly office hours
   on weekdays -> a call-centre profile. This became the rule in `int_internal_traffic` (checked afterwards against
   the simulated truth: precision and recall in `findings.json` `sim.e3.internal_rule`).
5. **Recompute the metric without internal traffic and robots** (`mart_linked_id_metrics`, scope
   `excl_internal_and_bots`): the tail collapses to households (2-3 accounts on a shared family device) and a small
   residual compatible with the measured false-positive rate.
6. **Recommend**: tag internal traffic (Fingerprint's `tags` / `linkedId` documentation), exclude it from fraud rules,
   keep a household rule (2-4 accounts) instead of treating any shared visitor as fraud. Deliver the corrected metric in
   the health report.

## Queries

```sql
-- accounts per visitor, three scopes
select * from mart_linked_id_metrics where customer_id = 'C07' order by scope;
-- suspected internal visitors
select visitor_id, accounts, heavy_visitors_on_network from int_internal_traffic
where customer_id = 'C07' and is_internal_suspected order by accounts desc;
```

## Decision tree

```
Visitor with many accounts?
 |- 20+ accounts, shared network with other heavy visitors -> internal traffic (agents, QA devices): tag and exclude.
 |- 2-4 accounts, home network, long history             -> shared household device: expected, not an error.
 |- accounts with no common network or time pattern      -> possible false positives: playbook false_positive_investigation.
```

## Message template

> The visitor ids that group hundreds of your accounts are your own support agents' computers (same office networks,
> office hours). That is correct identification of their devices, not a mistake. Excluding them, a visitor id is
> linked to [mean] accounts on average and [p99] at most for 99% of visitors, which matches shared family devices.
> We recommend tagging internal traffic so your fraud rules ignore it.
