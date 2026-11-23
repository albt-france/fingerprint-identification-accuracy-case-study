# Glossary

| Term | Meaning |
|---|---|
| Device fingerprint | A combination of browser and device attributes that is stable enough to recognise a device without a cookie. In this project: an illustrative 16-attribute combination on 2013 data. |
| Deterministic identification | The answer comes from a signal that identifies the visitor directly (for example a first-party cookie). |
| Probabilistic identification | The answer is inferred from attributes that many devices can share. |
| Control set / test set | Fingerprint's accuracy experiment: deterministic events (control) re-identified without their deterministic signal (test). |
| True positive (TP) | Recognised as the right existing visitor. |
| False positive (FP) | Recognised as another existing visitor: two people merged. |
| False negative (FN) | A returning visitor treated as new: one person split. |
| True negative (TN) | A new visitor treated as new. |
| Confidence score | 1 - estimated probability of a false positive; 1.0 for a new visitor. |
| Calibration | Agreement between the score and the observed error rate. |
| Anonymity set | The group of users sharing the same fingerprint. |
| Entropy (Shannon) | Information carried by an attribute, in bits: H = -sum p log2 p. |
| Grain | What one row means (event, visit, user-day). Rates change with the grain. |
| Visit | The first event of a user after 30 minutes of inactivity. |
| linkedId | An identifier of the customer's own (an account id) sent with the identification request, to build customer-specific metrics. |
| Internal traffic | Requests from the customer's own staff (support agents) that log into many accounts. |
| Proxy integration | Routing identification requests through the customer's own domain; without it, ad blockers block part of them. |
| Control share | Share of events answered deterministically. |
| Mix effect / Simpson's paradox | A total rate moves because the composition changes, not because any part changes. |
| Direct standardization | Recomputing a rate at a fixed reference mix. |
| Wilson interval | Confidence interval for a proportion, accurate for small rates. |
| Cluster bootstrap | Resampling visitors instead of events to respect their correlation. |
| Design effect / over-dispersion (phi) | How much clustering inflates the variance compared with independent events. |
| Minimal detectable effect | The smallest change a test can reliably detect with the data available. |
| Benjamini-Hochberg | A correction that controls the share of false alerts when testing many series. |
| Control chart (p'-chart) | A chart with limits that show when a rate leaves its normal range. |
| CUSUM | A cumulative sum that detects small persistent shifts. |
| Incremental model (dbt) | A model that only recomputes recent data on each run instead of rebuilding everything. |
| Lookback window | The days an incremental model recomputes on each run, to absorb late data. |
| dbt unit test | A test of a model's logic on hand-written input rows and expected output rows. |
| AggregatingMergeTree | A ClickHouse table engine that stores mergeable aggregate states (for example distinct-count states). |
| Materialized view | A ClickHouse view that transforms rows at insert time into a target table. |
| MCP (Model Context Protocol) | An open protocol that lets an AI assistant call tools (here: five read-only accuracy tools). |
| POC | Proof of concept: a prospect testing the product before buying. |
| Book of business | The set of customers a Customer Success pod is responsible for. |
| On-call | A rotation where one analyst answers alerts outside normal hours. |
| Step-up | An extra verification (for example a one-time code) asked when confidence is under a threshold. |
