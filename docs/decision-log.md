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
- [x] Update Patients Waiting, Waiting Over 12 Weeks and Patients Seen with the
      suppression guard
- [ ] Replace S08000030 with the board name once the PHS lookup table is available
- [ ] Note the gap in data-dictionary.md under the relevant fields

## 2026-10-01 — Health board lookup: four PHS reference tables appended into Ref_HealthBoard

**Context**
Dim_HealthBoard is a DAX calculated table built from codes in the fact tables, so it only contained codes (e.g. S08000030), which are unreadable on report pages and especially on the Health Board Deep Dive drillthrough page.
A check of the codes in use showed four sources were needed to label every code:
- S08 regional boards — PHS Geography Codes and Labels, *Health Board 2014 – Health Board 2019*
- SB special health boards — PHS Non Standard Geography Codes and Labels, *Special Health Boards and National Facilities*
- S27 codes — PHS Geography Codes and Labels, *ISD Health Board of Treatment*
- RA27 codes — PHS Non Standard Geography Codes and Labels, *Other Residential Categories*

**Decision**
- Each CSV stored in `data/bronze/<table>/<table>.csv` and loaded via `fnLoadBronzeTable` into a `src_` query (load disabled).
- Each `src_` query keeps only the code and name columns, renamed to a common schema `HB` / `HBName`.
- `Ref_HealthBoard` filters the health board table to current codes (`HBDateArchived` is null) and appends the three `src_` queries with `Table.Combine` (29 rows). The table is hidden and has no relationships.
- `Dim_HealthBoard[Board Name]` is a calculated column using `LOOKUPVALUE` against `Ref_HealthBoard`, with S92000003 hard-coded as "Scotland" (it only appears as a country code in the PHS tables) and `COALESCE` falling back to the raw code.
- All data sources set to the **Public** privacy level (PHS open data under OGL, public GitHub repo) rather than ignoring privacy levels.

**Rationale**
- Filtering archived codes is safe: none of the archived board codes (S08000018, 021, 023, 027) appear in the fact data, as PHS recodes historical records to current codes. Filtering also guarantees one name per code, which `LOOKUPVALUE` requires.
- A single appended lookup keeps the DAX simple: new code families can be added in Power Query without changing the model.

## 2026-10-01 — Encoding issue in special_health_boards.csv

**Context**
"The Golden Jubilee National Hospital" (SB0801) displayed as `The�Golden...`. Inspecting the raw bytes (`xxd`) showed the character between "The" and "Golden" is `0xA0` — a Latin-1/Windows-1252 non-breaking space — while the rest of the file is plain ASCII. A lone `0xA0` is invalid UTF-8, so reading the file with UTF-8 (`Encoding = 65001`, as used for all bronze files) produced the replacement character U+FFFD.

**Decision**
Bronze file left unchanged. In `src_SpecialHealthBoards`, the replacement character is replaced with a normal space and the value trimmed:
`Text.Trim(Text.Replace(_, Character.FromNumber(65533), " "))`.

**Rationale**
Bronze stays a faithful copy of the source; the fix is documented and reproducible in the transformation layer. Changing the encoding for the whole file was unnecessary because only one byte was affected.

## 2026-10-01 — Board Type classification and scope of board-level analysis

**Decision**
Calculated column `Dim_HealthBoard[Board Type]`, derived from the code prefix:

| Board Type | Rule | Codes in data |
|---|---|---|
| Scotland | S92000003 | 1 |
| Regional | starts with S08 | 14 |
| Special | starts with SB | 1 (SB0801, Golden Jubilee) |
| Other | everything else | 3 (S27000001, RA2702, RA2704) |

Board-level visuals and the Health Board Deep Dive drillthrough include **Regional** and **Special** only.

**Rationale**
- *Other* codes are not organisations that can be benchmarked or held accountable: S27000001 is "Non-NHS Provider/Location", RA2702 is "Resident of the Rest of United Kingdom (Outside Scotland)", RA2704 is "Unknown Residency". They are typically small and often suppressed, giving blank or volatile measures.
- *Scotland* is the benchmark on the deep dive page, so drilling into it would compare Scotland with itself.
- *Special* (Golden Jubilee) is a real NHS provider and is kept, but it treats national referrals rather than a regional population, so comparisons with the Scotland average need a caveat on the page.
- Classification uses code prefixes rather than the lookup tables, so it stays stable if label tables change.

**Open question**
The fact column is `HBT` (health board of treatment), yet it contains residence categories (RA27 codes). To confirm against the PHS waiting times data dictionary how these rows are assigned.

## 2026-10-02 — BoardSelected detection extended to Board Name

**Context**
All snapshot measures (Patients Waiting, Waiting Over 12 Weeks, Patients Seen, Median Wait (Days)) decide between the Scotland row (S92000003) and board rows using `ISFILTERED ( Dim_HealthBoard[HealthBoardCode] )`. When board visuals switched their axis to `Board Name`, this returned FALSE, so the measures selected the Scotland row while the board filter was still applied — every bar went blank.

**Decision**
`BoardSelected = ISFILTERED ( Dim_HealthBoard[HealthBoardCode] ) || ISFILTERED ( Dim_HealthBoard[Board Name] )` in all four measures.
`ISFILTERED ( Dim_HealthBoard )` (whole table) was rejected because a Board Type filter would then also count as "board selected".

**Rule that follows**
Board Type filters are applied at visual level only, on visuals whose axis is Board Name. A page-level Board Type filter would remove the Scotland row (Board Type = "Scotland") and blank the Scotland KPI cards.

## 2026-10-02 — Benchmark and prior-year measures on a month-end period table

**Context**
`Dim_Period` contains only month-end dates (monthly ongoing waits, quarterly completed waits), so built-in time intelligence (DATEADD, SAMEPERIODLASTYEAR) is not suitable.

**Decision**
- Scotland benchmark: `CALCULATE ( [measure], REMOVEFILTERS ( Dim_HealthBoard ) )`. Inside the base measure, BoardSelected becomes FALSE and the Scotland row is used automatically; date and patient type filters are preserved.
- 12 months ago: compute the current period with the same logic as the base measure's LatestPeriod, shift it with `EOMONTH ( CurrentPeriod, -12 )`, then evaluate the base measure with `REMOVEFILTERS ( Dim_Period )` and `Dim_Period[PeriodEndDate] = PriorPeriod`. EOMONTH keeps quarter-end dates aligned for quarterly data.
- Differences of two percentages are reported as percentage points (labelled "pp"); Patients Waiting change is a percentage change.

**Validation**
Checked in a test table: Scotland column constant and equal to the Overview card; board minus Scotland equals the "vs Scotland" column; prior-year value minus change equals current value.

## 2026-10-02 — Health Board Deep Dive: drillthrough and PatientType handling

**Decision**
- Drillthrough field: `Dim_HealthBoard[Board Name]`, source visuals filtered to Regional and Special boards.
- **Keep all filters turned off**; PatientType carried between pages by **synced slicers** instead.

**Rationale**
With Keep all filters on, the source page's PatientType selection arrived as a drillthrough filter, which also restricted the slicer on the deep dive page to that single value, so users could not switch patient type. Synced slicers keep the selection consistent across pages while leaving it changeable.
The PatientType slicer is single-select because Median Wait (Days) only returns a value for a single row (medians cannot be summed across patient types).

**Other page behaviour**
- Dynamic title from `Deep Dive Title` (`SELECTEDVALUE` of Board Name, with a usage hint when no board is selected).
- `Special Board Note` shows a caveat only when Board Type = "Special" (Golden Jubilee, a national referral centre); returns an empty string otherwise.
- Trend charts use linear lines: smooth interpolation created artificial peaks between quarterly median points.