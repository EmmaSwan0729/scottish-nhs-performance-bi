# Decision Log

Entries are in chronological order. Where a later decision changes an earlier one,
the earlier entry is marked and points forward.

## Phase 1 — Load data from source URLs instead of local files

**Status**
Superseded on 2026-09-27 (see "Bronze layer on GitHub").

**Decision**
Data was loaded directly from PHS open data download links via the Power Query Web
connector, so the report could be refreshed without manual downloads.

## 2026-09-27 — Bronze layer on GitHub during PHS outage

**Context**
opendata.nhs.scot was down (confirmed externally).

**Decision**
The two fact files already downloaded were committed to `data/bronze/`, and Power BI
reads them from raw.githubusercontent.com via `GitHubRepoPath` and `fnLoadBronzeTable`.

**Status**
Lookup tables were pending at the time. Resolved 1–2 Oct: health board and specialty
lookups added to bronze.

## 2026-09-27 — Latest period must be global, not per entity

**Context**
Board RA2702 has no June 2026 record; its latest month is May 2026.
`MAX(PeriodEndDate)` evaluated per board mixed periods in the board comparison
(RA2702 showed 100%).

**Decision**
LatestPeriod removes board, specialty and patient type filters, so all entities are
compared at the same point in time.

**Note**
Since 2026-10-02 the specialty part uses `REMOVEFILTERS ( Dim_Specialty )`
(see "Measures detect specialty selection on Dim_Specialty").

## 2026-09-27 — Two fact tables need conformed dimensions

**Context**
Both fact tables have `HealthBoardCode`. Slicing an Ongoing measure by the Completed
table's column silently returned the Scotland value for every board, because the
tables are not related.

**Decision**
Phase 2 introduces shared dimension tables (Dim_Period, Dim_PatientType,
Dim_HealthBoard, later Dim_Specialty), each related 1:* to both fact tables.

## 2026-09-30 — Scotland-level gap in stage of treatment data (2017–2018)

**Context**
While building page 2 (Activity & Throughput), the Patients Waiting line dropped
sharply around 2018, and Patients Seen had no values for several quarters.

**Finding**
- The gap comes from the PHS source data, not from our Power Query cleaning.
- In both bronze files, the Scotland total rows (HBT = S92000003, Specialty = Z9)
  exist for the affected periods, but the values are null and the QF column is
  flagged `:` (PHS: data not available).
- Root cause: one NHS board, **S08000030 (NHS Tayside)**, did not submit data. PHS
  therefore did not publish a national total rather than publishing an understated one.
- Affected periods:

| Dataset | Patient type | Missing Scotland total |
|---|---|---|
| Ongoing Waits (monthly) | Inpatient/Day case | Apr 2017 – Jun 2018 |
| Ongoing Waits (monthly) | New Outpatient | Apr 2017 – Dec 2018 |
| Completed Waits (quarterly) | Inpatient/Day case | Q2 2017 – Q2 2018 |
| Completed Waits (quarterly) | New Outpatient | Q2 2017 – Q4 2018 |

- All other boards reported normally, so board-level views are not affected.

**Risk**
Jul–Dec 2018 is the dangerous period: Inpatient is present but New Outpatient is not.
Without a guard, measures with no patient type filter silently return the Inpatient
figure as if it were the total (~74k instead of ~370k).

**Decision**
- Measures return BLANK if any row in scope has a PHS-suppressed value, instead of
  summing the remaining rows. Partial totals are never shown.
- Charts showing Scotland-level trends carry a note explaining the gap.
- Board-level visuals are left as they are.

**How it was verified**
Checked with pandas against data/bronze/ongoing_waits and data/bronze/completed_waits:
filtered to HBT = S92000003 and Specialty = Z9, pivoted by period and PatientType, then
checked which S08 boards had null values in the gap months (only S08000030).

**Follow-ups**
- [x] Update Patients Waiting, Waiting Over 12 Weeks and Patients Seen with the
      suppression guard
- [x] Replace S08000030 with the board name once the PHS lookup table is available
      (done 2026-10-01 via Ref_HealthBoard)
- [x] Note the gap in data-dictionary.md under the relevant fields

## 2026-10-01 — Health board lookup: four PHS reference tables appended into Ref_HealthBoard

**Context**
Dim_HealthBoard is a DAX calculated table built from codes in the fact tables, so it
only contained codes (e.g. S08000030), which are unreadable on report pages and
especially on the Health Board Deep Dive drillthrough page. A check of the codes in
use showed four sources were needed to label every code:
- S08 regional boards — PHS Geography Codes and Labels, *Health Board 2014 – Health Board 2019*
- SB special health boards — PHS Non Standard Geography Codes and Labels, *Special Health Boards and National Facilities*
- S27 codes — PHS Geography Codes and Labels, *ISD Health Board of Treatment*
- RA27 codes — PHS Non Standard Geography Codes and Labels, *Other Residential Categories*

**Decision**
- Each CSV stored in `data/bronze/<table>/<table>.csv` and loaded via
  `fnLoadBronzeTable` into a `src_` query (load disabled).
- Each `src_` query keeps only the code and name columns, renamed to a common schema
  `HB` / `HBName`.
- `Ref_HealthBoard` filters the health board table to current codes
  (`HBDateArchived` is null) and appends the three `src_` queries with
  `Table.Combine` (29 rows). The table is hidden and has no relationships.
- `Dim_HealthBoard[Board Name]` is a calculated column using `LOOKUPVALUE` against
  `Ref_HealthBoard`, with S92000003 hard-coded as "Scotland" (it only appears as a
  country code in the PHS tables) and `COALESCE` falling back to the raw code.
- All data sources set to the **Public** privacy level (PHS open data under OGL,
  public GitHub repo) rather than ignoring privacy levels.

**Why**
- Filtering archived codes is safe: none of the archived board codes (S08000018,
  021, 023, 027) appear in the fact data, as PHS recodes historical records to
  current codes. Filtering also guarantees one name per code, which `LOOKUPVALUE`
  requires.
- A single appended lookup keeps the DAX simple: new code families can be added in
  Power Query without changing the model.

## 2026-10-01 — Encoding issue in special_health_boards.csv

**Context**
"The Golden Jubilee National Hospital" (SB0801) displayed as `The�Golden...`.
Inspecting the raw bytes (`xxd`) showed the character between "The" and "Golden" is
`0xA0` — a Latin-1/Windows-1252 non-breaking space — while the rest of the file is
plain ASCII. A lone `0xA0` is invalid UTF-8, so reading the file with UTF-8
(`Encoding = 65001`, as used for all bronze files) produced the replacement character
U+FFFD.

**Decision**
Bronze file left unchanged. In `src_SpecialHealthBoards`, the replacement character
is replaced with a normal space and the value trimmed:
`Text.Trim(Text.Replace(_, Character.FromNumber(65533), " "))`.
`Ref_Specialty` applies the same guard to SpecialtyName.

**Why**
Bronze stays a faithful copy of the source; the fix is documented and reproducible in
the transformation layer. Changing the encoding for the whole file was unnecessary
because only one byte was affected.

## 2026-10-01 — Board Type classification and scope of board-level analysis

**Decision**
Calculated column `Dim_HealthBoard[Board Type]`, derived from the code prefix:

| Board Type | Rule | Codes in data |
|---|---|---|
| Scotland | S92000003 | 1 |
| Regional | starts with S08 | 14 |
| Special | starts with SB | 1 (SB0801, Golden Jubilee) |
| Other | everything else | 3 (S27000001, RA2702, RA2704) |

Board-level visuals and the Health Board Deep Dive drillthrough include **Regional**
and **Special** only.

**Why**
- *Other* codes are not organisations that can be benchmarked or held accountable:
  S27000001 is "Non-NHS Provider/Location", RA2702 is "Resident of the Rest of United
  Kingdom (Outside Scotland)", RA2704 is "Unknown Residency". They are typically small
  and often suppressed, giving blank or volatile measures.
- *Scotland* is the benchmark on the deep dive page, so drilling into it would compare
  Scotland with itself.
- *Special* (Golden Jubilee) is a real NHS provider and is kept, but it treats
  national referrals rather than a regional population, so comparisons with the
  Scotland average need a caveat on the page.
- Classification uses code prefixes rather than the lookup tables, so it stays stable
  if label tables change.

**Open question**
The fact column is `HBT` (health board of treatment), yet it contains residence
categories (RA27 codes). To confirm against the PHS waiting times data dictionary how
these rows are assigned.

## 2026-10-02 — BoardSelected detection extended to Board Name

**Status**
Revised later the same day (see "BoardSelected also checks Board Type").

**Context**
All snapshot measures (Patients Waiting, Waiting Over 12 Weeks, Patients Seen, Median
Wait (Days)) decide between the Scotland row (S92000003) and board rows using
`ISFILTERED ( Dim_HealthBoard[HealthBoardCode] )`. When board visuals switched their
axis to `Board Name`, this returned FALSE, so the measures selected the Scotland row
while the board filter was still applied — every bar went blank.

**Decision**
`BoardSelected = ISFILTERED ( Dim_HealthBoard[HealthBoardCode] ) || ISFILTERED ( Dim_HealthBoard[Board Name] )`
in all four measures. `ISFILTERED ( Dim_HealthBoard )` (whole table) was rejected
because a Board Type filter would then also count as "board selected".

**Rule that follows**
Board Type filters are applied at visual level only. A page-level Board Type filter
would remove the Scotland row (Board Type = "Scotland") and blank the Scotland KPI
cards.

## 2026-10-02 — Benchmark and prior-year measures on a month-end period table

**Context**
`Dim_Period` contains only month-end dates (monthly ongoing waits, quarterly completed
waits), so built-in time intelligence (DATEADD, SAMEPERIODLASTYEAR) is not suitable.

**Decision**
- Scotland benchmark: `CALCULATE ( [measure], REMOVEFILTERS ( Dim_HealthBoard ) )`.
  Inside the base measure, BoardSelected becomes FALSE and the Scotland row is used
  automatically; date and patient type filters are preserved.
- 12 months ago: compute the current period with the same logic as the base measure's
  LatestPeriod, shift it with `EOMONTH ( CurrentPeriod, -12 )`, then evaluate the
  base measure with `REMOVEFILTERS ( Dim_Period )` and
  `Dim_Period[PeriodEndDate] = PriorPeriod`. EOMONTH keeps quarter-end dates aligned
  for quarterly data.
- Differences of two percentages are reported as percentage points (labelled "pp");
  Patients Waiting change is a percentage change.

**Validation**
Checked in a test table: Scotland column constant and equal to the Overview card;
board minus Scotland equals the "vs Scotland" column; prior-year value minus change
equals current value.

## 2026-10-02 — Health Board Deep Dive: drillthrough and PatientType handling

**Decision**
- Drillthrough field: `Dim_HealthBoard[Board Name]`, source visuals filtered to
  Regional and Special boards.
- **Keep all filters turned off**; PatientType carried between pages by **synced
  slicers** instead.

**Why**
With Keep all filters on, the source page's PatientType selection arrived as a
drillthrough filter, which also restricted the slicer on the deep dive page to that
single value, so users could not switch patient type. Synced slicers keep the
selection consistent across pages while leaving it changeable. The PatientType slicer
is single-select because Median Wait (Days) only returns a value for a single row
(medians cannot be summed across patient types).

**Other page behaviour**
- Dynamic title from `Deep Dive Title` (`SELECTEDVALUE` of Board Name, with a usage
  hint when no board is selected).
- `Special Board Note` shows a caveat only when Board Type = "Special" (Golden
  Jubilee, a national referral centre); returns an empty string otherwise.
- Trend charts use linear lines: smooth interpolation created artificial peaks between
  quarterly median points.

## 2026-10-02 — Ongoing Waits is monthly, not quarterly (correction)

**Context**
Early notes described `MonthEnding` as quarterly.

**Decision**
Treat ongoing_waits as a monthly snapshot; completed_waits remains quarterly.

**Why**
Values such as 20170430 and 20180930 are not quarter ends. Data dictionary updated.

## 2026-10-02 — Blank specialty codes replaced with UNSPEC

**Context**
Some fact rows have no specialty code (including NHS GGC's unlisted XSU). A blank key
on the one side of a relationship blocked Dim_Specialty.

**Decision**
Replace blank/null `SpecialtyCode` with `UNSPEC` in both fact queries
(FillBlankSpecialty step) and add `UNSPEC` = "Unspecified / unlisted" to
Ref_Specialty. Dim_Specialty also filters blanks as a safeguard.

**Why**
Keeps the rows visible with a meaningful label instead of an unexplained "(Blank)"
member.

**Note**
Power BI auto-detected relationships from both fact tables to Ref_Specialty when it was loaded. These were deleted: Ref_Specialty, like Ref_HealthBoard, is a lookup-only table with no relationships.

## 2026-10-02 — Measures detect specialty selection on Dim_Specialty

**Context**
Measures used `ISFILTERED ( Fact_*[SpecialtyCode] )` and
`REMOVEFILTERS ( Fact_*[SpecialtyCode] )`. Filters from Dim_Specialty arrive through
the relationship, so specialty visuals returned blank and the latest period was
computed per specialty.

**Decision**
`SpecialtySelected` checks `Dim_Specialty[SpecialtyCode]` and
`Dim_Specialty[Specialty Name]`; latest-period variables use
`REMOVEFILTERS ( Dim_Specialty )`.

**Why**
Same root cause as the earlier Board Name bug: a measure must check the columns that
visuals actually filter on.

## 2026-10-02 — BoardSelected also checks Board Type

**Context**
The board × specialty matrix uses Top N by Patients Waiting plus a Board Type filter.
Top N is evaluated without row headers, so the measure fell back to the Scotland row,
which the Board Type filter excludes; the matrix came back empty.

**Decision**
Add `ISFILTERED ( Dim_HealthBoard[Board Type] )` to `BoardSelected` in the four base
measures.

**Why**
Any filter on board attributes now means "break down by board". Pages 1–3 are
unaffected because their Board Type filters already sit on visuals with Board Name on
the axis.

**Supersedes**
The earlier Board Name entry rejected counting Board Type as a board selection. That
held while Board Type filters only appeared on visuals with Board Name on the axis;
Top N on the matrix showed it is needed. HealthBoardCode, Board Name and Board Type
are listed explicitly rather than using `ISFILTERED ( Dim_HealthBoard )`, so any
future column on the table is a deliberate addition.

## 2026-10-02 — Specialty visuals exclude All Specialties at visual level

**Decision**
`Is All Specialties = False` is applied per visual, never as a page filter.

**Why**
Same rule as Board Type: page-level filters would blank out cards that need Scotland
totals.

## 2026-10-02 — Page 4 defaults to New Outpatient

**Decision**
The Patient Type slicer is saved on New Outpatient, and the key-points text box states
that view.

**Why**
Outpatients are the larger volume, and the narrative is static text, so it must match
the default view.

**Note**
The slicer is synced across pages, so this also sets the default view on pages 2
and 3.

## 2026-10-02 — .pbix kept out of Git

**Decision**
`*.pbix` added to .gitignore; dated local backups kept outside the repo. TMDL is the
version-controlled source of the model.

**Why**
Binary files cannot be diffed, duplicate the bronze data and bloat the repo. A .pbix
can later be attached to a GitHub Release for reviewers.

## 2026-10-03 — P90 Wait (Days) measure

**Context**
Median wait alone hides how long the slowest patients wait. PHS publishes a 90th percentile (`P90Days`) alongside the median in the completed waits file, so the report should show the long tail as well (report question 2).

**Decision**
- Added `P90 Wait (Days)` to `Fact_CompletedWaits`, copied from `Median Wait (Days)` with only the value column changed (`MedianDays` → `P90Days`).
- Same logic as the median: latest period by default, Scotland total (`S92000003`) unless a board is filtered, All Specialties (`Z9`) unless a specialty is filtered, and a value only when exactly one row is in scope. So the measure needs a single PatientType and returns BLANK when the PHS value is suppressed (`:` / `:u` qualifiers).
- Page 2: P90 card under the Median card, and P90 as a second line on the median wait trend chart (renamed "Median and 90th percentile wait over time (days)"). Format: whole number.

**Why**
Reusing the median pattern keeps both measures behaving identically under every filter combination. Validated against the raw `P90Days` column for Scotland / Z9 by PatientType: values match, P90 ≥ median in every period, and the Apr 2017–Dec 2018 gap returns BLANK, not 0.

### 2026-10-03 — Methodology change: 2023 waiting times guidance (from 30 Jul 2025)

**Context**
From 30 Jul 2025 PHS calculates waits under the Scottish Government's 2023 waiting times guidance. A patient's clock can now be reset or paused even after 12 weeks (e.g. after a cancellation or non-attendance), so some reported waits are shorter. Waiting list sizes and activity counts are unaffected. For completed waits this is a clean break in trend; ongoing waits open at 30 Jul 2025 were recalculated, so earlier month-ends are a mix of old and new rules.

PHS's extended impact assessment (28 Apr 2026, Mar 2025–Mar 2026) shows the effect on completed waits:
- Inpatient/Day case P90: 478 → 433 days reported (−45); under 2012 rules 467 (−11).
- New Outpatient P90: 373 → 335 days reported (−38); under 2012 rules 351 (−22).
- Median: reported roughly flat, but would have risen under 2012 rules (Inpatient/Day case +15 days vs +5 reported).

**Decision**
- No adjustment to the data: the report shows PHS official statistics as published.
- Added a dashed constant line "2023 guidance (Jul 2025)" at 30 Jul 2025 on the page 2 median/P90 trend chart, and a chart note explaining that much of the 2025/26 fall in P90 reflects the rule change rather than faster treatment.
- Wait-length figures after Jul 2025 are not treated as directly comparable with earlier quarters in any written conclusion (README, chart notes).

**Why**
Without the annotation, the post-2025 drop in P90 reads as a genuine improvement. For Inpatient/Day case, roughly three-quarters of the reported fall is due to the rule change. Flagging it keeps the report's conclusions honest while still using the official figures.

Source: PHS impact assessment – 2023 Waiting Times Guidance, extension covering 1 Mar 2025 to 31 Mar 2026 (published 28 Apr 2026).

### 2026-10-03 — Quarters to Clear List measure

**Context**
Report question 5 asks whether the system can keep up. The combo chart on page 2 shows patients seen vs the waiting list, but leaves the reader to compare two series on very different scales. A single ratio makes the backlog easier to read: how many quarters of current activity it would take to clear the current list.

**Decision**
- Added `Quarters to Clear List` to `Fact_CompletedWaits`: `Patients Waiting` (month-end) ÷ `Patients Seen` (quarterly), both evaluated at the same period end.
- The period is anchored to the completed waits table: `SeenPeriod` is the latest `PeriodEndDate` in `Fact_CompletedWaits` within the current period filter (board, patient type and specialty filters removed, as in the median pattern). `Patients Waiting` and `Patients Seen` are then both evaluated at `Dim_Period[PeriodEndDate] = SeenPeriod`.
- Returns BLANK unless exactly one PatientType is in scope (`HASONEVALUE`), the period exists in the quarterly table, and both values are present with `Patients Seen > 0`.
- Page 2: card under the P90 card; line chart "Quarters to clear the waiting list" (linear lines, continuous axis) with a dashed constant line "COVID-19 (Mar 2020)" at 23 Mar 2020 and an explanatory note.
- Format: decimal, 1 place.
- Page 3: fourth KPI card for the drilled-through board, with a "vs Scotland" reference label. Benchmark measures `Quarters to Clear List (Scotland)` (`REMOVEFILTERS(Dim_HealthBoard)`) and `Quarters to Clear vs Scotland` (difference, format `+0.0;-0.0;0.0`), same pattern as the other benchmark measures.
- No 12-months-ago card on page 3: the Patients Waiting card already shows "vs 12 months ago" as a reference label.

**Why**
- *Period alignment:* ongoing waits are monthly and completed waits are quarterly. Anchoring to the latest quarter end prevents a card from dividing, say, a July list by June activity once the next monthly release lands ahead of the quarterly one. On the trend chart, non-quarter months return BLANK automatically, so points appear only at quarter ends.
- *Single patient type:* adding outpatient appointments to inpatient/day case admissions and then dividing has no clear meaning, so the total row and multi-select contexts return BLANK.
- *Interpretation:* the ratio assumes no new referrals. It is a backlog indicator, not an actual wait, and is described that way in the chart note and README.
- *Not affected by the 2023 guidance:* both inputs are counts, which PHS confirms are unchanged by the Jul 2025 rule change, so no methodology line is needed on this chart.

Validated against manual calculation from a check table: Jun 2026 = 2.3 (Inpatient/Day case, 157,191 ÷ 67,674) and 1.5 (New Outpatient, 496,349 ÷ 320,424); Mar 2026 = 2.1 and 1.4; Dec 2012 New Outpatient = 0.6; non-quarter months and the total row are BLANK.

**Note — series start (Dec 2012):** Inpatient/Day case shows 1.0 in the first quarter, against roughly 0.6 for the following quarters. Patients Seen in that quarter (45,805) is well below later quarters (around 80,000), and the inpatient waiting list roughly doubles between Oct 2012 and mid-2013. This is likely an incomplete start to the series rather than a real change. Kept as published; to verify against PHS metadata.

### 2026-10-03 — Patients Waiting vs pre-COVID baseline

**Context**
Report question 1 asks whether the waiting list has recovered since COVID. A 12-month comparison shows the recent direction but not whether the list is back to where it was.

**Decision**
- Added `Patients Waiting (Pre-COVID)` (Patients Waiting at `Dim_Period[PeriodEndDate] = 29 Feb 2020`) and `Patients Waiting vs Pre-COVID %` to the Benchmark folder in `Fact_OngoingWaits`.
- Shown as a "vs pre-COVID (Feb 2020)" reference label on the page 1 Patients waiting card, below "vs 12 months ago". Card only; not used on trend charts.

**Why**
- *Baseline month:* Feb 2020 is the last month-end before lockdown (23 Mar 2020); the Mar 2020 figure is already partly affected.
- *Comparability:* list size is a count, which PHS confirms is unaffected by the Jul 2025 guidance change, so the comparison holds across the whole period.

Validated: Feb 2020 baseline = 79,025 (Inpatient/Day case) and 269,222 (New Outpatient); Jun 2026 vs baseline = +98.9% and +84.4%.