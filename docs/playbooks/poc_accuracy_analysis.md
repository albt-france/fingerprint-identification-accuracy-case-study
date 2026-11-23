# Playbook: accuracy analysis for a POC (prospect)

**Trigger**: a Sales Engineer runs a proof of concept and needs an accuracy readout, or the prospect questions the results.

## 1. Before the POC starts (with the SE)

- Agree on the **success metric** in the prospect's words (for example "visitors per account", "share of returning
  devices recognised", "share of risky logins flagged") and map it to our definitions (METRICS.md).
- Ask for `linkedId` on login events: it enables customer-specific metrics.
- **Minimum duration**: compute the minimal detectable effect from the expected traffic (`docs/statistics_notes.md`);
  with typical POC volumes, two weeks are a floor, and partial first / last weeks are flagged.
- Agree that **robots are reported separately**: their traffic is not identification of people.

## 2. Readout structure

1. Volumes and traffic mix (browsers, mobile share, private browsing, robot share).
2. Accuracy on human traffic, by segment, with intervals.
3. Customer-specific metrics with and without robots and internal traffic.
4. Limits: duration, segments with too little data, what the control-set measurement cannot see (private browsing).

## 3. Decision tree when the POC "looks bad"

```
Visitors per account (or new-visitor share) jumped?
 |- bad-robot share jumped at the same time? -> segment robots out; show human-only metrics; share the robot report.
 |- incognito share jumped?                  -> mix change, explain the measurement limit.
 |- one browser version?                     -> check the platform series (drift?).
 |- none of these                            -> integration review with the SE (script placement, linkedId mapping).
```

## 4. Worked example (SIMULATED): P01, "visitors per account exploded this week"

- During 2026-11-05 to 2026-11-12 bad robots made up about 4 in 10 of P01's requests (robot monitor alert on day one).
- With robots, visitors per account went from about 1.5 to 2.5. Removing the **flagged** robots is not enough: the
  measured FN rate stayed about twice its usual level, because some robots are not flagged and leak into the rates.
  On genuinely human traffic (known only because the data is simulated) the FN rate was unchanged. In a real POC,
  the residual is chased with the robot report (networks, versions, hours) before reading accuracy.
- Readout: report human accuracy separately, show the robot wave as a finding in itself (it is exactly the kind of
  traffic the prospect wants to detect). Numbers: report page 7, `findings.json` `sim.e6`.
- No description of how the robots behave or avoid detection is given or needed.

## 5. Message template for the SE

> The jump is robot traffic: [x]% of requests between [dates] were flagged as bad robots. On human traffic, accuracy is
> stable at [rates]. We suggest presenting human accuracy and the robot detection as two results; the robot wave is a
> good illustration of what the product catches.
