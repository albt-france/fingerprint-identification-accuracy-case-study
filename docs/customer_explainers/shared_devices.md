# "One visitor ID groups many of our accounts": what we found

*Customer note · SIMULATED example (fictional customer and platform) · one page*

## Your question

You saw visitor IDs linked to many of your customer accounts, some to hundreds, and asked whether the service was
mixing up your customers.

## What we found

We looked at every visitor ID linked to more than a handful of accounts.

- **The ones linked to hundreds of accounts are your own support team's computers.** About forty computers, on three
  of your office networks, used during office hours on weekdays, each opening many customer accounts. The service
  recognised those computers correctly: it is the same computer every time. It is simply used by an agent to look at
  many accounts.
- **The ones linked to two or three accounts are mostly shared family devices**: a tablet or a laptop used by several
  people of the same household, each with their own account.
- What is left is a small number of genuine mix-ups, in line with the usual accuracy of the service.

When we leave out your support computers, a visitor ID is linked to about one account on average, and to two
accounts at most for 99 visitors out of 100.

## What we recommend

1. **Mark your internal traffic.** When your agents use the service, send a tag saying it is internal. Your fraud rules
   can then ignore it, and your reports will no longer show those computers.
2. **Allow for households.** A visitor ID with two to four accounts on the same home connection is usually a family,
   not fraud. A rule that blocks any shared device would block genuine customers.
3. **Use the corrected measure** in your reports: "accounts per visitor, internal traffic excluded". It is now in your
   monthly health report.

*Independent case study based on public data · not affiliated with or endorsed by Fingerprint*
