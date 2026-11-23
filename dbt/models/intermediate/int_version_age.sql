-- Age of the browser version on each day: days since the REAL first stable release of that major version.
-- Chrome Mobile and Edge follow the Chromium milestone calendar (Edge ships a few days later: approximation);
-- Safari, Mobile Safari and iOS apps follow the iOS calendar. Unknown versions get NULL.
with combos as (
    select distinct browser, browser_major, event_date
    from {{ ref('stg_identification_events') }}
),
mapped as (
    select
        *,
        case
            when browser in ('Chrome', 'Chrome Mobile', 'Edge')            then 'Chrome'
            when browser = 'Firefox'                                       then 'Firefox'
            when browser in ('Mobile Safari', 'Safari', 'Native iOS')      then 'iOS'
        end as release_family
    from combos
)
select
    m.browser,
    m.browser_major,
    m.event_date,
    m.release_family,
    r.release_date,
    m.event_date - r.release_date as days_since_release,
    case
        when r.release_date is null                   then 'unknown'
        when m.event_date - r.release_date <= 7       then '0-7 days'
        when m.event_date - r.release_date <= 28      then '8-28 days'
        when m.event_date - r.release_date <= 90      then '29-90 days'
        else '>90 days'
    end as version_age_bucket
from mapped m
left join {{ ref('stg_browser_releases') }} r
    on r.release_family = m.release_family and r.major = m.browser_major
