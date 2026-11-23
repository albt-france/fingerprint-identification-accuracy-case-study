-- Question : replaying Fingerprint's accuracy experiment on the 30 largest sites, what share of events is
--            re-identified correctly (TP), merged with someone else (FP) or split off as new (FN)?
-- Grain    : EVENT (every page view is a re-identification attempt; repeated page views inflate TP, see 05)
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

-- name: 04_reid_event_grain
WITH top AS (SELECT CounterID FROM default.hits GROUP BY CounterID ORDER BY count() DESC LIMIT 30),
e AS (
    SELECT CounterID, UserID,
           row_number() OVER (PARTITION BY CounterID, fph ORDER BY EventTime, WatchID) AS fp_seq,
           lagInFrame(UserID) OVER (PARTITION BY CounterID, fph ORDER BY EventTime, WatchID
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_user,
           row_number() OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID) AS user_seq
    FROM (SELECT *, cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel) AS fph FROM default.hits WHERE CounterID IN top AND UserID != toInt64(0))
)
SELECT CounterID, count() AS events,
    countIf(fp_seq > 1 AND prev_user = UserID)  AS tp_n,   -- re-identified as the right visitor
    countIf(fp_seq > 1 AND prev_user != UserID) AS fp_n,   -- matched to ANOTHER existing visitor
    countIf(fp_seq = 1 AND user_seq > 1)        AS fn_n,   -- returning visitor wrongly seen as new
    countIf(fp_seq = 1 AND user_seq = 1)        AS tn_n    -- new visitor correctly seen as new
FROM e
GROUP BY CounterID
ORDER BY events DESC;
