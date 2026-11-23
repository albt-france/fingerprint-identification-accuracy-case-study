-- Question : how many users share the same fingerprint (anonymity set), on one day and over the month?
-- Grain    : fingerprint-day (15 July 2013, a complete weekday) and user-month
-- Definition: anonymity set of a fingerprint = number of distinct UserIDs seen with it.
--            A fingerprint seen with one UserID only is "unique".
-- Run      : run date, duration and row count of each statement in clickhouse/README.md

-- name: 03_anon_summary
WITH f AS (
    SELECT cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel) AS fph, uniqExact(UserID) AS users
    FROM default.hits
    WHERE EventDate = '2013-07-15' AND UserID != toInt64(0)
    GROUP BY fph
)
SELECT count() AS fingerprints, countIf(users = 1) AS unique_fps, countIf(users > 1) AS shared_fps,
       max(users) AS largest_set, sum(users) AS user_fp_pairs, sumIf(users, users = 1) AS users_in_unique_fps
FROM f;

-- name: 03_anon_buckets
-- Distribution of set sizes, split by device type (IsMobile of the fingerprint's events).
WITH f AS (
    SELECT cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel) AS fph, any(IsMobile) AS is_mobile, uniqExact(UserID) AS users
    FROM default.hits
    WHERE EventDate = '2013-07-15' AND UserID != toInt64(0)
    GROUP BY fph
)
SELECT is_mobile,
       multiIf(users = 1, '1', users = 2, '2', users <= 5, '3-5', users <= 20, '6-20', users <= 100, '21-100',
               users <= 1000, '101-1000', '>1000') AS set_size,
       count() AS fingerprints, sum(users) AS users_total
FROM f
GROUP BY is_mobile, set_size
ORDER BY is_mobile, min(f.users);

-- name: 03_attribute_sets_check
-- Distinct fingerprints on the same day with 18, 16 and 14 attributes (sensitivity of the attribute choice).
SELECT uniqExact(cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel, IsMobile, WindowClientWidth)) AS fp18, uniqExact(cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel)) AS fp16, uniqExact(cityHash64(OS, UserAgent, UserAgentMajor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, SilverlightVersion1, MobilePhoneModel)) AS fp14,
       uniqExact(UserID) AS users
FROM default.hits
WHERE EventDate = '2013-07-15' AND UserID != toInt64(0);

-- name: 03_fps_per_user_month
-- How many different fingerprints does one UserID show over the whole month? (instability of the fingerprint)
WITH u AS (
    SELECT UserID, uniqExact(cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel)) AS n_fp
    FROM default.hits
    WHERE UserID != toInt64(0)
    GROUP BY UserID
)
SELECT count() AS users, quantileExact(0.5)(n_fp) AS p50, quantileExact(0.9)(n_fp) AS p90,
       quantileExact(0.99)(n_fp) AS p99, avg(n_fp) AS mean_fp, countIf(n_fp > 1) / count() AS share_multi_fp
FROM u;
