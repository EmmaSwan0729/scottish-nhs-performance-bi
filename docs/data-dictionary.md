# Data Dictionary

## Sources

| Table | Source resource | Resource ID | Grain |
|---|---|---|---|
| Ongoing Waits | PHS Stage of Treatment Waiting Times – Ongoing Waits – Long Trend | 5816ec92-66bf-4033-ae55-9df45ff19d49 | Quarter × Health board × Patient type × Specialty |
| Completed Waits | PHS Stage of Treatment Waiting Times – Completed Waits – Long Trend | 4c091d26-1492-41e5-9577-832cbc1cd4cf | Quarter × Health board × Patient type × Specialty |

Data is loaded via the CKAN datastore dump endpoint
(`https://www.opendata.nhs.scot/datastore/dump/<resource_id>?bom=True`),
which always returns the latest file regardless of file name.
Coverage starts from quarter ending 31 Dec 2012.

## Ongoing Waits

| Column | Type | Meaning | Notes |
|---|---|---|---|
| MonthEnding | numeric (YYYYMMDD) | Last day of the quarter the data reports on | Named "Month" but is quarterly; completed table uses `QuarterEnding`. Standardise to one date column. |
| HBT | text | Health board of treatment (boundaries as at 1 April 2019) | Code only; label from Health Board / Country / Special Health Board lookups |
| HBTQF | text | Qualifier for HBT | See Qualifiers |
| PatientType | text | New Outpatient, Inpatient, Day case, etc. | Check distinct values |
| Specialty | text | Specialty of the clinician in charge | Code only; label from Specialty lookup. Specialty rows do not sum to "All Specialties" (low-volume specialties excluded). Blank code includes NHS GGC's unlisted code XSU. |
| SpecialtyQF | text | Qualifier for Specialty | See Qualifiers |
| NumberWaiting | numeric | Number of ongoing waits at quarter end | Additive across boards and patient types, not across specialties |
| NumberWaitingQF | text | Qualifier for NumberWaiting | |
| NumberWaitingOver12Weeks | numeric | Ongoing waits over 12 weeks | Same additivity as NumberWaiting |
| NumberWaitingOver12WeeksQF | text | Qualifier | |
| Median | numeric (days) | Median wait of ongoing waits | Non-additive: never sum or average across rows |
| MedianQF | text | Qualifier for Median | |
| 90thPercentile | numeric (days) | 90th percentile wait of ongoing waits | Non-additive |
| 90thPercentileQF | text | Qualifier for 90thPercentile | |

## Completed Waits

| Column | Type | Meaning | Notes |
|---|---|---|---|
| QuarterEnding | numeric (YYYYMMDD) | Last day of the quarter | |
| HBT / HBTQF | text | As Ongoing Waits | |
| PatientType | text | As Ongoing Waits | |
| Specialty / SpecialtyQF | text | As Ongoing Waits | Same caveats |
| NumberSeen | numeric | Completed waits (patients seen / admitted) in the quarter | Additive across boards and patient types, not across specialties |
| NumberSeenQF | text | Qualifier | |
| WaitedOver12Weeks | numeric | Completed waits that exceeded 12 weeks | Column name differs from ongoing (`NumberWaitingOver12Weeks`) |
| WaitedOver12WeeksQF | text | Qualifier | |
| Median | numeric (days) | Median wait of completed waits within the quarter | Non-additive |
| MedianQF | text | Qualifier | |
| 90thPercentile | numeric (days) | 90th percentile wait of completed waits within the quarter | Non-additive |
| 90thPercentileQF | text | Qualifier | |

## Qualifiers (QF columns)

Suppressed or missing values appear as empty cells, with the reason
recorded in the matching QF column. Common codes:

| Code | Meaning |
|---|---|
| c | Confidential (suppressed) |
| : | Not available |
| z | Not applicable |
| r | Revised since first published |

Full list: PHS Statistical Qualifiers lookup on opendata.nhs.scot.

## Lookup Tables

| Lookup | Joins on | Used for |
|---|---|---|
| Health Board labels | HBT | Dim_HealthBoard |
| Country labels | HBT | Scotland-level rows |
| Special Health Board labels | HBT | Special boards (e.g. national facilities) |
| Specialty codes | Specialty | Dim_Specialty |