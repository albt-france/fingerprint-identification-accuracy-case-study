# Privacy and ethics

## Device identification is personal data in Europe

Under the GDPR, an identifier that singles out a device or browser, and data linked to it, is personal data, and
reading or storing information on a user's device is also governed by the ePrivacy rules. Any real use of device
identification therefore needs:

- a **legal basis** (fraud prevention is commonly argued as a legitimate interest, which must be documented and balanced
  against the user's rights; some uses need consent);
- a **clear purpose** limited to it (here: fraud prevention and account security, not advertising);
- **data minimisation and retention limits**;
- transparency towards users, and a data processing agreement between the customer and the provider.

This document is a reminder, not legal advice.

## What this project does to stay on the safe side

- **No real visitor-level data is published.** The ClickBench `hits` rows were anonymised by their publisher; this
  project still only publishes **aggregates** (per site, per day, per bucket). The local copy stays in `data/raw/`.
- **No IP address, even hashed,** in any published file. The simulated `ip_hash` (a hash of a fictional network)
  is used inside the warehouse only and is removed from the published sample.
- **Simulated identifiers only** (`V...`, `ACC...`, `D...`), generated at random.
- The **self-service tools and the MCP server return aggregates only**: no event-level row, no visitor id, no
  account id, no network hash (tested in `tests/test_mcp_server.py` and `tests/test_tools.py`).
- **No browser-signal collection code** of any kind is included.
- **No guidance on evading identification or robot detection.** The project measures accuracy and explains errors;
  it never describes how a robot or a fraudster could avoid being identified.
- The illustrative fingerprint (16 attributes, exact or tolerant match) is a teaching device on 2013 data, not
  Fingerprint's algorithm and not a new technique.

## Fairness to customers and end users

A false positive can lock a legitimate user out or send them an extra one-time code; a false negative can let an
account takeover through. Health reports and explainers state both errors, their uncertainty and their limits in plain
language, and the recommendations always include the end-user cost (step-ups, friction).
