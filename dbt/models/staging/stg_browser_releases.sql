-- REAL release calendar. One row per browser and major version = its FIRST stable release
-- (the iOS rows marked "latest" are later point releases and are dropped by the qualify).
select
    browser                                   as release_family,
    cast(major as integer)                    as major,
    cast(release_date as date)                as release_date,
    first_stable_build,
    source
from {{ source('sim', 'browser_releases') }}
qualify row_number() over (partition by browser, major order by cast(release_date as date), first_stable_build) = 1
