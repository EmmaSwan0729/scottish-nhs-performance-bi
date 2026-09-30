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

## 2026-09-30 — Scotland-level gap in stage of treatment data (2017–2018)

### Context
While building page 2 (Activity & Throughput), the Patients Waiting line dropped sharply
around 2018, and Patients Seen had no values for several quarters.

### Finding
- The gap comes from the PHS source data, not from our Power Query cleaning.
- In both bronze files, the Scotland total rows (HBT = S92000003, Specialty = Z9) exist
  for the affected periods, but the values are null and the QF column is flagged `:`
  (PHS: data not available).
- Root cause: one NHS board, **S08000030**, did not submit data. PHS therefore did not
  publish a national total rather than publishing an understated one.
- Affected periods:

| Dataset | Patient type | Missing Scotland total |
|---|---|---|
| Ongoing Waits (monthly) | Inpatient/Day case | Apr 2017 – Jun 2018 |
| Ongoing Waits (monthly) | New Outpatient | Apr 2017 – Dec 2018 |
| Completed Waits (quarterly) | Inpatient/Day case | Q2 2017 – Q2 2018 |
| Completed Waits (quarterly) | New Outpatient | Q2 2017 – Q4 2018 |

- All other boards reported normally, so board-level views are not affected.

### Risk
Jul–Dec 2018 is the dangerous period: Inpatient is present but New Outpatient is not.
Without a guard, measures with no patient type filter silently return the Inpatient
figure as if it were the total (~74k instead of ~370k).

### Decision
- Measures return BLANK if any row in scope has a PHS-suppressed value, instead of
  summing the remaining rows. Partial totals are never shown.
- Charts showing Scotland-level trends carry a note explaining the gap.
- Board-level visuals are left as they are.

### How it was verified
Checked with pandas against data/bronze/ongoing_waits and data/bronze/completed_waits:
filtered to HBT = S92000003 and Specialty = Z9, pivoted by period and PatientType, then
checked which S08 boards had null values in the gap months (only S08000030).

### Follow-ups
- [ ] Update Patients Waiting, Waiting Over 12 Weeks and Patients Seen with the
      suppression guard
- [ ] Replace S08000030 with the board name once the PHS lookup table is available
- [ ] Note the gap in data-dictionary.md under the relevant fields