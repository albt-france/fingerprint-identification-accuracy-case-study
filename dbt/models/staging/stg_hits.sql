{{ config(materialized='view') }}
-- REAL ClickBench rows (local files hits_0..hits_4), dates converted, only the columns of the replay.
-- Users without a cookie (UserID = 0) have no ground truth and are excluded.
select
    CounterID                                          as counter_id,
    UserID                                             as user_id,
    WatchID                                            as watch_id,
    date '1970-01-01' + cast(EventDate as integer)     as event_date,
    to_timestamp(EventTime)                            as event_time,
    EventTime                                          as event_time_s,
    Robotness                                          as robotness,
    IsMobile                                           as is_mobile,
    -- the 16 attributes of the illustrative fingerprint (values obfuscated: only equality is meaningful)
    OS, UserAgent, UserAgentMajor, UserAgentMinor, ResolutionWidth, ResolutionHeight, ResolutionDepth,
    ClientTimeZone, BrowserLanguage, BrowserCountry, JavaEnable, CookieEnable, FlashMajor, FlashMinor,
    SilverlightVersion1, MobilePhoneModel
from {{ source('public', 'hits') }}
where UserID <> 0
