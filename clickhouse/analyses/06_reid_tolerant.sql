-- Question : what does a stricter or looser fingerprint do to the FP / FN trade-off?
-- Grain    : VISIT (see 05), 30 largest sites
-- Variants (strictest to loosest):
--   0 strict18   = 16 attributes + IsMobile + WindowClientWidth (window size changes often -> more FN)
--   1 exact16    = the reference fingerprint
--   2 tolerant14 = without UserAgentMinor and FlashMinor (absorbs minor browser / plugin updates)
--   3 loose9     = also without plugin flags and colour depth
--   4 loosest5   = OS, browser, screen size and time zone only (many collisions -> more FP)
--   ARRAY JOIN duplicates each visit start once per variant, so the five replays run in one pass.
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

-- The 30 sites are split in two statements (ranks 1-15 and 16-30) to stay under the 18.6 GiB memory limit.

-- name: 06_reid_tolerant_a
WITH top AS (SELECT CounterID FROM default.hits GROUP BY CounterID ORDER BY count() DESC LIMIT 15),
v AS (
    SELECT CounterID, UserID, EventTime, WatchID, h0, h1, h2, h3, h4,
           row_number() OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID) AS user_rn,
           lagInFrame(EventTime) OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_t
    FROM (SELECT CounterID, UserID, EventTime, WatchID,
                 cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel, IsMobile, WindowClientWidth) AS h0,
                 cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel) AS h1,
                 cityHash64(OS, UserAgent, UserAgentMajor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, SilverlightVersion1, MobilePhoneModel) AS h2,
                 cityHash64(OS, UserAgent, UserAgentMajor, ResolutionWidth, ResolutionHeight, ClientTimeZone, BrowserLanguage, BrowserCountry, MobilePhoneModel) AS h3,
                 cityHash64(OS, UserAgent, ResolutionWidth, ResolutionHeight, ClientTimeZone) AS h4
          FROM default.hits WHERE CounterID IN top AND UserID != toInt64(0))
),
s AS (
    -- keep visit starts first, THEN duplicate them once per variant (keeps memory under the playground limit)
    SELECT CounterID, UserID, EventTime, WatchID, fph, variant
    FROM (SELECT * FROM v WHERE user_rn = 1 OR dateDiff('second', prev_t, EventTime) > 1800)
    ARRAY JOIN [h0, h1, h2, h3, h4] AS fph, [0, 1, 2, 3, 4] AS variant
),
e AS (
    SELECT CounterID, UserID, variant,
           row_number() OVER (PARTITION BY CounterID, variant, fph ORDER BY EventTime, WatchID) AS fp_seq,
           lagInFrame(UserID) OVER (PARTITION BY CounterID, variant, fph ORDER BY EventTime, WatchID
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_user,
           row_number() OVER (PARTITION BY CounterID, variant, UserID ORDER BY EventTime, WatchID) AS user_seq
    FROM s
)
SELECT CounterID, variant, count() AS visits,
    countIf(fp_seq > 1 AND prev_user = UserID)  AS tp_n,   -- re-identified as the right visitor
    countIf(fp_seq > 1 AND prev_user != UserID) AS fp_n,   -- matched to ANOTHER existing visitor
    countIf(fp_seq = 1 AND user_seq > 1)        AS fn_n,   -- returning visitor wrongly seen as new
    countIf(fp_seq = 1 AND user_seq = 1)        AS tn_n    -- new visitor correctly seen as new
FROM e
GROUP BY CounterID, variant
ORDER BY CounterID, variant;

-- name: 06_reid_tolerant_b
WITH top AS (SELECT CounterID FROM default.hits GROUP BY CounterID ORDER BY count() DESC LIMIT 15 OFFSET 15),
v AS (
    SELECT CounterID, UserID, EventTime, WatchID, h0, h1, h2, h3, h4,
           row_number() OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID) AS user_rn,
           lagInFrame(EventTime) OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_t
    FROM (SELECT CounterID, UserID, EventTime, WatchID,
                 cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel, IsMobile, WindowClientWidth) AS h0,
                 cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel) AS h1,
                 cityHash64(OS, UserAgent, UserAgentMajor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, SilverlightVersion1, MobilePhoneModel) AS h2,
                 cityHash64(OS, UserAgent, UserAgentMajor, ResolutionWidth, ResolutionHeight, ClientTimeZone, BrowserLanguage, BrowserCountry, MobilePhoneModel) AS h3,
                 cityHash64(OS, UserAgent, ResolutionWidth, ResolutionHeight, ClientTimeZone) AS h4
          FROM default.hits WHERE CounterID IN top AND UserID != toInt64(0))
),
s AS (
    -- keep visit starts first, THEN duplicate them once per variant (keeps memory under the playground limit)
    SELECT CounterID, UserID, EventTime, WatchID, fph, variant
    FROM (SELECT * FROM v WHERE user_rn = 1 OR dateDiff('second', prev_t, EventTime) > 1800)
    ARRAY JOIN [h0, h1, h2, h3, h4] AS fph, [0, 1, 2, 3, 4] AS variant
),
e AS (
    SELECT CounterID, UserID, variant,
           row_number() OVER (PARTITION BY CounterID, variant, fph ORDER BY EventTime, WatchID) AS fp_seq,
           lagInFrame(UserID) OVER (PARTITION BY CounterID, variant, fph ORDER BY EventTime, WatchID
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_user,
           row_number() OVER (PARTITION BY CounterID, variant, UserID ORDER BY EventTime, WatchID) AS user_seq
    FROM s
)
SELECT CounterID, variant, count() AS visits,
    countIf(fp_seq > 1 AND prev_user = UserID)  AS tp_n,   -- re-identified as the right visitor
    countIf(fp_seq > 1 AND prev_user != UserID) AS fp_n,   -- matched to ANOTHER existing visitor
    countIf(fp_seq = 1 AND user_seq > 1)        AS fn_n,   -- returning visitor wrongly seen as new
    countIf(fp_seq = 1 AND user_seq = 1)        AS tn_n    -- new visitor correctly seen as new
FROM e
GROUP BY CounterID, variant
ORDER BY CounterID, variant;
