-- Question : same replay, but one identification request per VISIT (closer to a real identification call)
--            or per user-day: how much do the rates change with the grain?
-- Grain    : VISIT = first event of a UserID on a site after 30 minutes of inactivity;
--            DAY   = first event of a UserID on a site each day.
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

-- name: 05_reid_visit_grain
WITH top AS (SELECT CounterID FROM default.hits GROUP BY CounterID ORDER BY count() DESC LIMIT 30),
v AS (
    SELECT CounterID, UserID, EventDate, EventTime, WatchID, Robotness, IsMobile, fph,
           row_number() OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID) AS user_rn,
           lagInFrame(EventTime) OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_t
    FROM (SELECT *, cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel) AS fph FROM default.hits WHERE CounterID IN top AND UserID != toInt64(0))
),
s AS (SELECT * FROM v WHERE user_rn = 1 OR dateDiff('second', prev_t, EventTime) > 1800),
e AS (
    SELECT CounterID, UserID,
           row_number() OVER (PARTITION BY CounterID, fph ORDER BY EventTime, WatchID) AS fp_seq,
           lagInFrame(UserID) OVER (PARTITION BY CounterID, fph ORDER BY EventTime, WatchID
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_user,
           row_number() OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID) AS user_seq
    FROM s
)
SELECT CounterID, count() AS visits,
    countIf(fp_seq > 1 AND prev_user = UserID)  AS tp_n,   -- re-identified as the right visitor
    countIf(fp_seq > 1 AND prev_user != UserID) AS fp_n,   -- matched to ANOTHER existing visitor
    countIf(fp_seq = 1 AND user_seq > 1)        AS fn_n,   -- returning visitor wrongly seen as new
    countIf(fp_seq = 1 AND user_seq = 1)        AS tn_n    -- new visitor correctly seen as new
FROM e
GROUP BY CounterID
ORDER BY visits DESC;

-- name: 05_reid_day_grain
WITH top AS (SELECT CounterID FROM default.hits GROUP BY CounterID ORDER BY count() DESC LIMIT 30),
d AS (
    -- first event of each user-day: a GROUP BY with min() of a tuple uses far less memory than a window
    SELECT CounterID, UserID, t.1 AS EventTime, t.2 AS WatchID, t.3 AS fph
    FROM (
        SELECT CounterID, UserID, EventDate, min((EventTime, WatchID, cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel))) AS t
        FROM default.hits WHERE CounterID IN top AND UserID != toInt64(0)
        GROUP BY CounterID, UserID, EventDate
    )
),
e AS (
    SELECT CounterID, UserID,
           row_number() OVER (PARTITION BY CounterID, fph ORDER BY EventTime, WatchID) AS fp_seq,
           lagInFrame(UserID) OVER (PARTITION BY CounterID, fph ORDER BY EventTime, WatchID
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_user,
           row_number() OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID) AS user_seq
    FROM d
)
SELECT CounterID, count() AS user_days,
    countIf(fp_seq > 1 AND prev_user = UserID)  AS tp_n,   -- re-identified as the right visitor
    countIf(fp_seq > 1 AND prev_user != UserID) AS fp_n,   -- matched to ANOTHER existing visitor
    countIf(fp_seq = 1 AND user_seq > 1)        AS fn_n,   -- returning visitor wrongly seen as new
    countIf(fp_seq = 1 AND user_seq = 1)        AS tn_n    -- new visitor correctly seen as new
FROM e
GROUP BY CounterID
ORDER BY user_days DESC;
