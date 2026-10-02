# Data Dictionary

All source data comes from Public Health Scotland (PHS) open data
(opendata.nhs.scot). Raw files are stored unchanged in `data/bronze/`
and loaded into Power BI from GitHub
(`raw.githubusercontent.com/EmmaSwan0729/scottish-nhs-performance-bi/main/data/bronze/...`)
via the `GitHubRepoPath` parameter and the `fnLoadBronzeTable` function.

Why GitHub rather than the PHS endpoint: the Azure subscription was
disabled and opendata.nhs.scot had an outage from 26 Sep 2026, so the
CSVs were committed to the repo as the bronze layer (see decision-log).

## Sources

| Bronze table | Path | PHS source | Resource ID | Grain |
|---|---|---|---|---|
| ongoing_waits | data/bronze/ongoing_waits/ongoing_waits.csv | Stage of Treatment Waiting Times – Ongoing Waits – Long Trend | 5816ec92-66bf-4033-ae55-9df45ff19d49 | Month end × Health board × Patient type × Specialty |
| completed_waits | data/bronze/completed_waits/completed_waits.csv | Stage of Treatment Waiting Times – Completed Waits – Long Trend | 4c091d26-1492-41e5-9577-832cbc1cd4cf | Quarter × Health board × Patient type × Specialty |
| health_board_lookup | data/bronze/health_board_lookup/health_board_lookup.csv | Geography Codes and Labels – Health Board 2014/2019 (hb14_hb19) | – | One row per health board code |
| special_health_boards | data/bronze/special_health_boards/special_health_boards.csv | Non-standard Geography Codes and Labels – Special Health Boards and National Facilities | – | One row per special board code |
| isd_health_board_of_treatment | data/bronze/isd_health_board_of_treatment/isd_health_board_of_treatment.csv | Geography Codes and Labels – ISD Health Board of Treatment | – | One row per code |
| other_residential_categories | data/bronze/other_residential_categories/other_residential_categories.csv | Non-standard Geography Codes and Labels – Other Residential Categories | – | One row per code |
| specialty | data/bronze/specialty/specialty.csv | Specialty reference (TBC) | TBC | One row per specialty code |

Coverage: ongoing_waits from <20121031>, completed_waits from <20121031>.

Original PHS endpoint (for when the pipeline moves upstream):
`https://www.opendata.nhs.scot/datastore/dump/<resource_id>?bom=True`,
which always returns the latest file regardless of file name.

## Fact tables

### ongoing_waits

Snapshot of patients still waiting at the end of each month.

| Column | Type | Meaning | Notes |
|---|---|---|---|
| MonthEnding | numeric (YYYYMMDD) | Last day of the month the snapshot refers to | Monthly. Converted to `PeriodEndDate` (date) in Power Query |
| HBT | text | Health board of treatment code (boundaries as at 1 April 2019) | Code only. Renamed `HealthBoardCode`. Includes Scotland (S92000003), regional boards (S08), a special board (SB0801) and non-board categories (S27, RA27); see Lookup tables |
| HBTQF | text | Qualifier for HBT | See Qualifiers |
| PatientType | text | Patient type | Values: `Inpatient/Day case`, `New Outpatient` |
| Specialty | text | Specialty of the clinician in charge | Code only. Renamed `SpecialtyCode`. `Z9` = All Specialties. Specialty rows do not sum to Z9 (low-volume specialties excluded). Blank codes (including NHS GGC's unlisted XSU) are replaced with `UNSPEC` in Power Query |
| SpecialtyQF | text | Qualifier for Specialty | See Qualifiers |
| NumberWaiting | numeric | Patients waiting at month end | Additive across boards and patient types, not across specialties |
| NumberWaitingQF | text | Qualifier for NumberWaiting | |
| NumberWaitingOver12Weeks | numeric | Of those, waiting more than 12 weeks | Same additivity as NumberWaiting |
| NumberWaitingOver12WeeksQF | text | Qualifier | |
| Median | numeric (days) | Median wait of ongoing waits | Non-additive: never sum or average across rows |
| MedianQF | text | Qualifier for Median | |
| 90thPercentile | numeric (days) | 90th percentile wait of ongoing waits | Non-additive |
| 90thPercentileQF | text | Qualifier for 90thPercentile | |

### completed_waits

Patients who finished waiting (seen or admitted) during each quarter.

| Column | Type | Meaning | Notes |
|---|---|---|---|
| QuarterEnding | numeric (YYYYMMDD) | Last day of the quarter | Converted to `PeriodEndDate` (date) in Power Query |
| HBT / HBTQF | text | As ongoing_waits | Renamed `HealthBoardCode` |
| PatientType | text | As ongoing_waits | |
| Specialty / SpecialtyQF | text | As ongoing_waits | Renamed `SpecialtyCode`; same caveats |
| NumberSeen | numeric | Completed waits (patients seen / admitted) in the quarter | Additive across boards and patient types, not across specialties |
| NumberSeenQF | text | Qualifier | |
| WaitedOver12Weeks | numeric | Completed waits that exceeded 12 weeks | Name differs from `NumberWaitingOver12Weeks` in ongoing_waits |
| WaitedOver12WeeksQF | text | Qualifier | |
| Median | numeric (days) | Median wait of completed waits within the quarter | Non-additive |
| MedianQF | text | Qualifier | |
| 90thPercentile | numeric (days) | 90th percentile wait of completed waits within the quarter | Non-additive |
| 90thPercentileQF | text | Qualifier | |

### Known data gap

PHS did not publish Scotland totals for Apr 2017 – Jun 2018 (Inpatient/Day case)
and Apr 2017 – Dec 2018 (New Outpatient), because board S08000030 did not
submit data. Scotland-level values for these months are empty. Measures return
BLANK when any in-scope row is suppressed, and charts carry a note
(see decision-log).

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

## Lookup tables

PHS data files contain codes only; labels come from separate reference files.

### Health board lookups → Ref_HealthBoard

Four reference files are appended into one hidden Power Query table
`Ref_HealthBoard` (columns `HB`, `HBName`). Each source query keeps only its
code and name columns, renames them to `HB` / `HBName`, and has load disabled.

| Bronze table | Original columns used | Example codes | Notes |
|---|---|---|---|
| health_board_lookup | HB, HBName (also HBDateEnacted, HBDateArchived, Country) | S08000030 → NHS Tayside | Contains 4 archived codes (S08000018, S08000021, S08000023, S08000027) after the 2018/2019 boundary changes; filtered to HBDateArchived = null |
| special_health_boards | SHB, SHBName (also Country) | SB0801 → The Golden Jubilee National Hospital | |
| isd_health_board_of_treatment | ISDHBT, ISDHBTName | S27000001 → Non-NHS Provider/Location | S27000002 (Not applicable) is not present in the fact data |
| other_residential_categories | CustomResidency, CustomResidencyName | RA2702 → Resident of the Rest of UK (Outside Scotland); RA2704 → Unknown Residency | Residency categories appearing in HBT; exact PHS rule still to confirm |

Encoding note: "Golden Jubilee" contains a Latin-1 non-breaking space (0xA0).
It is fixed in Power Query; the bronze file is left unchanged.

Scotland (S92000003) is not in these files. Its label is set directly in the
Board Name column, and the Country lookup was not downloaded.

### Specialty lookup → Ref_Specialty

| Bronze table | Original columns used | Notes |
|---|---|---|
| specialty | Specialty, SpecialtyName | Specialty renamed to `SpecialtyCode`; SpecialtyName kept. Two rows added in Power Query: `Z9` = All Specialties and `UNSPEC` = Unspecified / unlisted (neither is in the source file) |

Some related specialties use separate codes (e.g. Endocrinology, Diabetes,
and Endocrinology & Diabetes) because boards code them differently. They are
kept separate rather than merged.

## Model dimensions derived from the data

| Dimension | Built from | Key columns | Notes |
|---|---|---|---|
| Dim_Period | Both fact tables (DAX) | PeriodEndDate, Year, Month Label, Month Sort | Month-end dates only, not a continuous calendar |
| Dim_PatientType | Both fact tables (DAX) | PatientType | |
| Dim_HealthBoard | Both fact tables (DAX) + Ref_HealthBoard | HealthBoardCode, Board Name, Board Type | Board Type by code prefix: S08 = Regional, SB = Special, S92 = Scotland, other = Other |
| Dim_Specialty | Both fact tables (DAX) + Ref_Specialty | SpecialtyCode, Specialty Name, Is All Specialties | Blank codes filtered out as a safeguard; Is All Specialties = TRUE only for Z9 |

Measures are documented separately (planned: `docs/measures.md`).