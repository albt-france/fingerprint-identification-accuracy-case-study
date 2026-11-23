-- Question : inside one real month, a browser moves from one major version to the next. Does the fingerprint
--            of the users who update become unstable (a real "drift after an update")?
-- Grain    : browser-version-day (10_ua_major_daily) and user-month (10_upgrade_instability)
-- Definition: main browser = the most frequent UserAgent value. Values are obfuscated: a "version change" is a
--            change of the UserAgentMajor value; the order of versions is not interpretable.
--            fp16 = reference fingerprint; fp_no_version = fp16 without UserAgentMajor/Minor and Flash versions.
-- Run      : run date, duration and row count of each statement in clickhouse/README.md

-- name: 10_ua_major_daily
WITH topua AS (SELECT UserAgent FROM default.hits GROUP BY UserAgent ORDER BY count() DESC LIMIT 1)
SELECT EventDate, UserAgentMajor, uniqExact(UserID) AS users, count() AS events
FROM default.hits
WHERE UserAgent IN topua AND UserID != toInt64(0)
GROUP BY EventDate, UserAgentMajor
ORDER BY EventDate, users DESC;

-- name: 10_upgrade_instability
WITH topua AS (SELECT UserAgent FROM default.hits GROUP BY UserAgent ORDER BY count() DESC LIMIT 1),
u AS (
    SELECT UserID,
           uniqExact(UserAgentMajor) AS n_major,
           uniqExact(cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel)) AS n_fp,
           uniqExact(cityHash64(OS, UserAgent, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, SilverlightVersion1, MobilePhoneModel)) AS n_fp_no_version,
           uniqExact(EventDate) AS n_days
    FROM default.hits
    WHERE UserAgent IN topua AND UserID != toInt64(0)
    GROUP BY UserID
    HAVING n_days >= 2
)
SELECT n_major > 1 AS changed_major, count() AS users,
       avg(n_fp) AS mean_fp, countIf(n_fp > 1) / count() AS share_multi_fp,
       avg(n_fp_no_version) AS mean_fp_no_version, countIf(n_fp_no_version > 1) / count() AS share_multi_fp_no_version
FROM u
GROUP BY changed_major
ORDER BY changed_major;
