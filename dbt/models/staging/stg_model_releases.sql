select model_version, cast(release_date as date) as release_date, change, segment
from {{ source('sim', 'model_releases') }}
