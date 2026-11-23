# Playbook: reported false negatives ("you split my users")

**Trigger**: returning customers appear as new visitors, visitors-per-account rises, "new visitor" share jumps, or the
false-negative monitor alerts on a series.

## 1. Questions to ask the customer

1. Examples of accounts with several visitor ids, with timestamps and devices if known.
2. Did they ship a new app or web release, change their integration (domain, proxy, script loading), or launch a
   campaign bringing private-browsing traffic?
3. Are robots or automated tests hitting the login page?
4. Which metric are they looking at (visitors per account, new-visitor rate, their own "unknown device" rule)?

## 2. Queries

- `fct_accuracy_daily`: FN rate by browser x **version** and `version_age_bucket` (a new browser release is the first
  suspect); compare with the platform series of the same version.
- Incognito share and new-visitor share of the customer (`fct_accuracy_weekly_customer`): private browsing cannot be
  matched deterministically and is split more often.
- Bad-robot share (`bot_result = 'bad'`) and the robot monitor: robots look like a flood of new visitors.
- `mart_linked_id_metrics`, scope `excl_bad_bots`: visitors per account without robots.

## 3. Decision tree

```
Is the FN increase significant?
 |- no  -> explain with the interval, ask for more examples.
 |- yes -> Is it on one browser version released recently (version age 0-28 days)?
           |- yes, platform-wide -> model drift after a browser update: escalate to the identification engineers
           |                       with segment, release date (real calendar), size; follow until the fix.
           |- no  -> Did the bad-robot share rise?          -> segment robots (playbook poc_accuracy_analysis).
                     Did the incognito share rise?          -> mix change; measured accuracy is optimistic (C09 explainer).
                     Did the integration change?            -> check script loading, proxy integration, domain.
```

## 4. Worked example (SIMULATED): Chrome 155

- Real Chrome 155 stable date: 2026-09-23 (Chromium Dash). Simulated FN on that version tripled for 9 days.
- Few users were on it yet (Chrome roll-outs start slowly: the real Wikimedia uptake curve is under 7% after two
  weeks), so no customer-level series could see it. The **platform series by browser version**, compared with the rest
  of the Chrome family because a new version has no history of its own, alerted on 2026-09-26, three days after the
  release and before the mass roll-out.
- A model fix (simulated release of 2026-10-02) closed it. Report page 6, `findings.json` `sim.e1`.

## 5. Message template

> We saw a short increase of returning visitors treated as new on Chrome [version] between [dates], on all customers.
> It was fixed on [date], before most Chrome users had updated. For your traffic the effect was [n] identifications.
> No action is needed on your side.
