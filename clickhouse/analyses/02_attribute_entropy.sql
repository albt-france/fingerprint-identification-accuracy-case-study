-- Question : which browser attributes carry identifying information in this anonymised dataset?
-- Grain    : user-day (one profile per UserID on 2013-07-15 = attributes of its first event that day)
-- Definition: Shannon entropy in bits, computed by ClickHouse's entropy() aggregate:  H = -sum p(v) * log2 p(v).
--             "empty" = 0 for numbers, '' for strings. Values were obfuscated by clickhouse-obfuscator:
--             only equality between values is meaningful, never the value itself.
-- Why 16 attributes: the fingerprint keeps every stable browser/device attribute available in the table and drops
--             IsMobile (implied by UserAgent and MobilePhoneModel) and WindowClientWidth (window size, changes
--             whenever the window is resized). Both are measured here anyway, to show what they would add.
-- Run      : see clickhouse/README.md

-- name: 02_attribute_entropy
WITH u AS (
    SELECT
        UserID,
        argMin(OS, (EventTime, WatchID)) AS OS,
        argMin(UserAgent, (EventTime, WatchID)) AS UserAgent,
        argMin(UserAgentMajor, (EventTime, WatchID)) AS UserAgentMajor,
        argMin(UserAgentMinor, (EventTime, WatchID)) AS UserAgentMinor,
        argMin(ResolutionWidth, (EventTime, WatchID)) AS ResolutionWidth,
        argMin(ResolutionHeight, (EventTime, WatchID)) AS ResolutionHeight,
        argMin(ResolutionDepth, (EventTime, WatchID)) AS ResolutionDepth,
        argMin(ClientTimeZone, (EventTime, WatchID)) AS ClientTimeZone,
        argMin(BrowserLanguage, (EventTime, WatchID)) AS BrowserLanguage,
        argMin(BrowserCountry, (EventTime, WatchID)) AS BrowserCountry,
        argMin(JavaEnable, (EventTime, WatchID)) AS JavaEnable,
        argMin(CookieEnable, (EventTime, WatchID)) AS CookieEnable,
        argMin(FlashMajor, (EventTime, WatchID)) AS FlashMajor,
        argMin(FlashMinor, (EventTime, WatchID)) AS FlashMinor,
        argMin(SilverlightVersion1, (EventTime, WatchID)) AS SilverlightVersion1,
        argMin(MobilePhoneModel, (EventTime, WatchID)) AS MobilePhoneModel,
        argMin(IsMobile, (EventTime, WatchID)) AS IsMobile,
        argMin(WindowClientWidth, (EventTime, WatchID)) AS WindowClientWidth
    FROM default.hits
    WHERE EventDate = '2013-07-15' AND UserID != toInt64(0)
    GROUP BY UserID
)
SELECT
    count() AS users,
    entropy(OS) AS h__OS, uniqExact(OS) AS n__OS, countIf(OS = 0) / count() AS empty__OS,
    entropy(UserAgent) AS h__UserAgent, uniqExact(UserAgent) AS n__UserAgent, countIf(UserAgent = 0) / count() AS empty__UserAgent,
    entropy(UserAgentMajor) AS h__UserAgentMajor, uniqExact(UserAgentMajor) AS n__UserAgentMajor, countIf(UserAgentMajor = 0) / count() AS empty__UserAgentMajor,
    entropy(UserAgentMinor) AS h__UserAgentMinor, uniqExact(UserAgentMinor) AS n__UserAgentMinor, countIf(UserAgentMinor = '') / count() AS empty__UserAgentMinor,
    entropy(ResolutionWidth) AS h__ResolutionWidth, uniqExact(ResolutionWidth) AS n__ResolutionWidth, countIf(ResolutionWidth = 0) / count() AS empty__ResolutionWidth,
    entropy(ResolutionHeight) AS h__ResolutionHeight, uniqExact(ResolutionHeight) AS n__ResolutionHeight, countIf(ResolutionHeight = 0) / count() AS empty__ResolutionHeight,
    entropy(ResolutionDepth) AS h__ResolutionDepth, uniqExact(ResolutionDepth) AS n__ResolutionDepth, countIf(ResolutionDepth = 0) / count() AS empty__ResolutionDepth,
    entropy(ClientTimeZone) AS h__ClientTimeZone, uniqExact(ClientTimeZone) AS n__ClientTimeZone, countIf(ClientTimeZone = 0) / count() AS empty__ClientTimeZone,
    entropy(BrowserLanguage) AS h__BrowserLanguage, uniqExact(BrowserLanguage) AS n__BrowserLanguage, countIf(BrowserLanguage = '') / count() AS empty__BrowserLanguage,
    entropy(BrowserCountry) AS h__BrowserCountry, uniqExact(BrowserCountry) AS n__BrowserCountry, countIf(BrowserCountry = '') / count() AS empty__BrowserCountry,
    entropy(JavaEnable) AS h__JavaEnable, uniqExact(JavaEnable) AS n__JavaEnable, countIf(JavaEnable = 0) / count() AS empty__JavaEnable,
    entropy(CookieEnable) AS h__CookieEnable, uniqExact(CookieEnable) AS n__CookieEnable, countIf(CookieEnable = 0) / count() AS empty__CookieEnable,
    entropy(FlashMajor) AS h__FlashMajor, uniqExact(FlashMajor) AS n__FlashMajor, countIf(FlashMajor = 0) / count() AS empty__FlashMajor,
    entropy(FlashMinor) AS h__FlashMinor, uniqExact(FlashMinor) AS n__FlashMinor, countIf(FlashMinor = 0) / count() AS empty__FlashMinor,
    entropy(SilverlightVersion1) AS h__SilverlightVersion1, uniqExact(SilverlightVersion1) AS n__SilverlightVersion1, countIf(SilverlightVersion1 = 0) / count() AS empty__SilverlightVersion1,
    entropy(MobilePhoneModel) AS h__MobilePhoneModel, uniqExact(MobilePhoneModel) AS n__MobilePhoneModel, countIf(MobilePhoneModel = '') / count() AS empty__MobilePhoneModel,
    entropy(IsMobile) AS h__IsMobile, uniqExact(IsMobile) AS n__IsMobile, countIf(IsMobile = 0) / count() AS empty__IsMobile,
    entropy(WindowClientWidth) AS h__WindowClientWidth, uniqExact(WindowClientWidth) AS n__WindowClientWidth, countIf(WindowClientWidth = 0) / count() AS empty__WindowClientWidth,
    entropy(cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel)) AS h__fingerprint16,
    uniqExact(cityHash64(OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth, ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor, SilverlightVersion1, MobilePhoneModel)) AS n__fingerprint16
FROM u;
