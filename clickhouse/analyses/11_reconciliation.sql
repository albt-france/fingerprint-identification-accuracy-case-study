-- Question : do DuckDB (local Parquet copy, dbt model int_hits_reid) and ClickHouse (playground) give exactly the
--            same replay results? Cross-engine reconciliation of the same metric definition.
-- Scope    : the 67 sites whose rows are ALL inside the local files hits_0..hits_4 (local row count = ClickHouse
--            row count). Sites cut between files, or continuing in files 5..99, are excluded (data/README.md).
-- Grain    : event and visit (see 04 and 05). Here the fingerprint is the tuple of the 16 attribute columns itself
--            (PARTITION BY the columns), not a hash, because DuckDB has no cityHash64: both engines then group
--            exactly the same rows.
-- Run      : run date, duration and row count in clickhouse/README.md

-- name: 11_reconciliation
WITH base AS (
    SELECT CounterID, UserID, EventTime, WatchID, OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel,
           row_number() OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID) AS user_rn,
           lagInFrame(EventTime) OVER (PARTITION BY CounterID, UserID ORDER BY EventTime, WatchID
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_t
    FROM default.hits
    WHERE CounterID IN (17, 20, 38, 49, 52, 59, 786, 1055, 1060, 1072, 1089, 1092, 1490, 1499, 1508, 1519, 1525, 1530, 1534, 1558, 1566, 1576, 1587, 1806, 1813, 1828, 1830, 1831, 1838, 1850, 1852, 1886, 1892, 1904, 1906, 1919, 1943, 1997, 2004, 2013, 2032, 2047, 2072, 2122, 2131, 2145, 2151, 2180, 2218, 2222, 2238, 3638, 3654, 3663, 3665, 3676, 3703, 3728, 3763, 3769, 3780, 3786, 3794, 3832, 3866, 3878, 3920) AND UserID != toInt64(0)
),
g AS (
    SELECT *, grain FROM base
    ARRAY JOIN ['event', 'visit'] AS grain
    WHERE grain = 'event' OR user_rn = 1 OR dateDiff('second', prev_t, EventTime) > 1800
),
e AS (
    SELECT CounterID, grain, UserID,
           row_number() OVER (PARTITION BY CounterID, grain, OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel ORDER BY EventTime, WatchID) AS fp_seq,
           lagInFrame(UserID) OVER (PARTITION BY CounterID, grain, OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel ORDER BY EventTime, WatchID
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_user,
           row_number() OVER (PARTITION BY CounterID, grain, UserID ORDER BY EventTime, WatchID) AS user_seq
    FROM g
)
SELECT CounterID, grain, count() AS n, uniqExact(UserID) AS users,
    countIf(fp_seq > 1 AND prev_user = UserID)  AS tp_n,
    countIf(fp_seq > 1 AND prev_user != UserID) AS fp_n,
    countIf(fp_seq = 1 AND user_seq > 1)        AS fn_n,
    countIf(fp_seq = 1 AND user_seq = 1)        AS tn_n
FROM e
GROUP BY CounterID, grain
ORDER BY CounterID, grain;
