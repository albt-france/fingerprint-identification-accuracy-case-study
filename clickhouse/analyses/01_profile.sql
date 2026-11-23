-- Question : how big is the real dataset, which days and sites does it cover, how many robots?
-- Grain    : event (one row of default.hits = one page view or event sent by a browser)
-- Definition: "user" = UserID (first-party cookie of the web-analytics service), "site" = CounterID.
--             uniq() is ClickHouse's approximate distinct count (HyperLogLog-like), uniqExact() is exact:
--             the gap is measured once here and uniqExact is used everywhere else.
-- Run      : see data/cache/clickhouse/<name>.json (run date, duration); filled in clickhouse/README.md

-- name: 01_profile_totals
SELECT
    count()                               AS events,
    uniqExact(UserID)                     AS users_exact,
    uniq(UserID)                          AS users_uniq_approx,
    uniqExact(CounterID)                  AS sites,
    min(EventDate)                        AS first_day,
    max(EventDate)                        AS last_day,
    uniqExact(EventDate)                  AS days_present,
    countIf(UserID = toInt64(0))          AS events_without_userid,
    countIf(Robotness > 0) / count()      AS bot_share,
    countIf(IsMobile = 1) / count()       AS mobile_share
FROM default.hits;

-- name: 01_profile_daily
-- Coverage by day: only 17 of the 30 July days exist and volumes are very uneven,
-- so the study never plots raw daily counts, only rates.
SELECT
    EventDate,
    count()                               AS events,
    uniqExact(UserID)                     AS users,
    uniqExact(CounterID)                  AS sites,
    countIf(Robotness > 0) / count()      AS bot_share,
    countIf(IsArtifical = 1) / count()    AS artificial_share
FROM default.hits
GROUP BY EventDate
ORDER BY EventDate;

-- name: 01_profile_sites
-- One row per site: volume, number of days covered (2 to 6 for most sites), bot and mobile shares.
SELECT
    CounterID,
    count()                               AS events,
    uniqExact(UserID)                     AS users,
    uniqExact(EventDate)                  AS days,
    min(EventDate)                        AS first_day,
    max(EventDate)                        AS last_day,
    countIf(Robotness > 0) / count()      AS bot_share,
    countIf(IsMobile = 1) / count()       AS mobile_share
FROM default.hits
GROUP BY CounterID
ORDER BY events DESC;
