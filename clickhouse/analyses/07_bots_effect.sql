-- Question : how much do robots change the measured accuracy?
-- Grain    : VISIT (see 05), 30 largest sites. Robot = Robotness > 0 on the visit's first event
--            (the analytics service's own robot flag). Two runs: all traffic (excl_bots = 0) and robots removed
--            BEFORE the replay (excl_bots = 1), because robots also pollute the history used for matching.
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

-- name: 07_bots_effect
WITH top AS (SELECT CounterID FROM default.hits GROUP BY CounterID ORDER BY count() DESC LIMIT 30),
v AS (
    SELECT CounterID, UserID, EventDate, EventTime, WatchID, Robotness, IsMobile, fph,
           row_number() OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID) AS user_rn,
           lagInFrame(EventTime) OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_t
    FROM (SELECT *, cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel) AS fph FROM default.hits WHERE CounterID IN top AND UserID != toInt64(0))
),
s AS (SELECT * FROM v WHERE user_rn = 1 OR dateDiff('second', prev_t, EventTime) > 1800),
b AS (
    SELECT CounterID, UserID, EventTime, WatchID, fph, Robotness, excl_bots
    FROM s ARRAY JOIN [0, 1] AS excl_bots
    WHERE NOT (excl_bots = 1 AND Robotness > 0)
),
e AS (
    SELECT CounterID, UserID, excl_bots, toUInt8(Robotness > 0) AS is_bot,
           row_number() OVER (PARTITION BY CounterID, excl_bots, fph ORDER BY EventTime, WatchID) AS fp_seq,
           lagInFrame(UserID) OVER (PARTITION BY CounterID, excl_bots, fph ORDER BY EventTime, WatchID
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_user,
           row_number() OVER (PARTITION BY CounterID, excl_bots, UserID ORDER BY EventTime, WatchID) AS user_seq
    FROM b
)
SELECT CounterID, excl_bots, is_bot, count() AS visits,
    countIf(fp_seq > 1 AND prev_user = UserID)  AS tp_n,   -- re-identified as the right visitor
    countIf(fp_seq > 1 AND prev_user != UserID) AS fp_n,   -- matched to ANOTHER existing visitor
    countIf(fp_seq = 1 AND user_seq > 1)        AS fn_n,   -- returning visitor wrongly seen as new
    countIf(fp_seq = 1 AND user_seq = 1)        AS tn_n    -- new visitor correctly seen as new
FROM e
GROUP BY CounterID, excl_bots, is_bot
ORDER BY CounterID, excl_bots, is_bot;
