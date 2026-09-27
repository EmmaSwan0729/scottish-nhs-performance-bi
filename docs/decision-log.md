# Decision Log

## Phase 1

### Load data from source URLs instead of local files
Data is loaded directly from PHS open data download links via the
Power Query Web connector, so the report can be refreshed without
manual downloads.

### 27th Sep
### Bronze layer on GitHub during PHS outage
opendata.nhs.scot was down (confirmed externally), so the two fact files
already downloaded were committed to `data/bronze/` and Power BI reads them
from raw.githubusercontent.com. Lookup tables are pending until PHS recovers.

### Latest period must be global, not per entity
Board RA2702 has no June 2026 record; its latest month is May 2026.
`MAX(PeriodEndDate)` evaluated per board mixed periods in the board
comparison (RA2702 showed 100%). LatestPeriod now removes board,
specialty and patient type filters so all entities are compared at the
same point in time.

### Two fact tables need conformed dimensions
Both fact tables have `HealthBoardCode`. Slicing an Ongoing measure by the
Completed table's column silently returned the Scotland value for every
board, because the tables are not related. Phase 2 introduces shared
dimension tables to prevent this.