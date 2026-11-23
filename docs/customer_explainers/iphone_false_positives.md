# Why some of your iPhone users were asked for an extra code

*Customer note · SIMULATED example (fictional customer and platform) · one page*

## What happened

Between mid-September and early October, some of your users on iPhones with the newest iOS version were asked for a
one-time code more often than usual when they logged in.

## Why

To recognise a returning device without asking the user anything, the service compares many characteristics of the
device. iPhones of the same model and the same iOS version look very much alike, so this is the hardest group to tell
apart. Right after the new iOS version came out, the service mixed up a few more of these iPhones than usual (about 5
in 100 recognitions in that group, against about 2 to 3 normally).

Each answer comes with a **confidence score**: a high score means "we are very sure this is the same device". For those
iPhones the scores were a little lower, and some fell under the level you chose to trigger an extra check (0.95).
So your extra-code rule did what it is meant to do: when we were less sure, it asked the user to confirm.

The scores were also slightly too optimistic: they announced fewer mix-ups than really happened. That is why we
corrected them, not only the recognition itself.

## What we did

- Our monitoring flagged this group the day after the iOS release, for all customers.
- A correction was released on 7 October. Since then the iPhone group is back to its usual level, and so is your
  extra-code rate.
- Your other users (computers, Android phones, older iPhones) were not affected.

## What you can do

Nothing is required. If you want fewer extra codes during future iOS releases, we can review your threshold with you:
a slightly lower threshold means fewer codes for genuine users, at the cost of catching fewer mix-ups. We will show you
both numbers before you decide.

*Independent case study based on public data · not affiliated with or endorsed by Fingerprint*
