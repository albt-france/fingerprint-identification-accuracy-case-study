-- Question : can a simple confidence score learnt on a site's first days still hold on its later days?
-- Grain    : VISIT (see 05), 30 largest sites, only visits that matched an earlier visitor (fp_seq > 1),
--            because Fingerprint defines confidence as 1 - probability of a false positive (a new visitor gets 1.0).
-- Score    : illustrative only. prior_users = number of distinct UserIDs already seen with this fingerprint
--            on the site before the visit (the anonymity set at that moment). src/findings.py learns
--            score(bucket) = 1 - FP share on the first half of each site's days and evaluates it on the second
--            half (reliability curve, expected calibration error).
-- Method   : Fingerprint's published accuracy experiment, replayed on real data
--            (https://docs.fingerprint.com/docs/identification-accuracy-and-confidence, read 2026-11-23):
--            control set = events identified deterministically (here: the UserID cookie);
--            test set    = the same events with the cookie removed, re-identified from the fingerprint only.
--            Re-identification policy (illustrative, NOT Fingerprint's algorithm): the event gets the UserID of
--            the LAST earlier event on the same site with the same fingerprint; no earlier match = new visitor.
--            TP = predicted visitor is the right one; FP = predicted visitor is another existing visitor;
--            FN = a returning visitor predicted as new; TN = a new visitor predicted as new.
--            Fingerprint = cityHash64 of 16 attributes (see 02). Order = (EventTime, WatchID), deterministic.
--            Users without a cookie (UserID = 0) are excluded: they have no ground truth.
-- Run      : run date, duration and row count of each statement in clickhouse/README.md

-- name: 08_confidence_calibration
WITH top AS (SELECT CounterID FROM default.hits GROUP BY CounterID ORDER BY count() DESC LIMIT 30),
v AS (
    SELECT CounterID, UserID, EventDate, EventTime, WatchID, Robotness, IsMobile, fph,
           row_number() OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID) AS user_rn,
           lagInFrame(EventTime) OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_t
    FROM (SELECT *, cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel) AS fph FROM default.hits WHERE CounterID IN top AND UserID != toInt64(0))
),
s AS (SELECT * FROM v WHERE user_rn = 1 OR dateDiff('second', prev_t, EventTime) > 1800),
w AS (
    SELECT CounterID, UserID, EventDate, EventTime, WatchID, fph,
           row_number() OVER (PARTITION BY CounterID, fph ORDER BY EventTime, WatchID) AS fp_seq,
           lagInFrame(UserID) OVER (PARTITION BY CounterID, fph ORDER BY EventTime, WatchID
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_user,
           toUInt32(row_number() OVER (PARTITION BY CounterID, fph, UserID ORDER BY EventTime, WatchID) = 1) AS first_pair
    FROM s
),
x AS (
    SELECT *,
           sum(first_pair) OVER (PARTITION BY CounterID, fph ORDER BY EventTime, WatchID
                                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) - first_pair AS prior_users,
           dense_rank() OVER (PARTITION BY CounterID ORDER BY EventDate) AS day_rank
    FROM w
)
SELECT CounterID, day_rank, least(prior_users, 100) AS prior_users_capped,
       count() AS matched_visits, countIf(prev_user != UserID) AS fp_n
FROM x
WHERE fp_seq > 1
GROUP BY CounterID, day_rank, prior_users_capped
ORDER BY CounterID, day_rank, prior_users_capped;
