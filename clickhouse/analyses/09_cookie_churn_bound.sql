-- Question : the cookie is not a perfect truth. How many measured false positives could be the SAME device
--            with a new cookie (cookies cleared)?
-- Grain    : VISIT (see 05), 30 largest sites, false-positive visits only.
-- Bound    : a FP links a visit of user B to an earlier user A. If A's activity on the site ends before B's
--            starts (no overlap), A and B may be one device whose cookie was reset -> "possibly churned cookie".
--            Overlapping activity means two cookies alive at the same time: a real collision.
--            This is an UPPER bound for cookie churn (no overlap is necessary, not sufficient).
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

-- name: 09_cookie_churn_bound
WITH top AS (SELECT CounterID FROM default.hits GROUP BY CounterID ORDER BY count() DESC LIMIT 30),
v AS (
    SELECT CounterID, UserID, EventDate, EventTime, WatchID, Robotness, IsMobile, fph,
           row_number() OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID) AS user_rn,
           lagInFrame(EventTime) OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_t
    FROM (SELECT *, cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel) AS fph FROM default.hits WHERE CounterID IN top AND UserID != toInt64(0))
),
s AS (SELECT * FROM v WHERE user_rn = 1 OR dateDiff('second', prev_t, EventTime) > 1800),
spans AS (
    SELECT CounterID, UserID, min(EventTime) AS t0, max(EventTime) AS t1
    FROM default.hits WHERE CounterID IN top AND UserID != toInt64(0)
    GROUP BY CounterID, UserID
),
e AS (
    SELECT CounterID, UserID,
           row_number() OVER (PARTITION BY CounterID, fph ORDER BY EventTime, WatchID) AS fp_seq,
           lagInFrame(UserID) OVER (PARTITION BY CounterID, fph ORDER BY EventTime, WatchID
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_user,
           row_number() OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID) AS user_seq
    FROM s
),
f AS (SELECT CounterID, UserID, prev_user FROM e WHERE fp_seq > 1 AND prev_user != UserID)
SELECT f.CounterID AS CounterID, count() AS fp_n,
       countIf(a.t1 < b.t0) AS fp_nonoverlap,
       countIf(dateDiff('second', a.t1, b.t0) > 86400) AS fp_gap_over_1day
FROM f
INNER JOIN spans AS a ON a.CounterID = f.CounterID AND a.UserID = f.prev_user
INNER JOIN spans AS b ON b.CounterID = f.CounterID AND b.UserID = f.UserID
GROUP BY f.CounterID
ORDER BY fp_n DESC;
