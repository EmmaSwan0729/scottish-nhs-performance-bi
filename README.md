# Scottish NHS Performance BI

Power BI analytics on NHS Scotland open data from Public Health Scotland,
focusing on stage of treatment waiting times across NHS health boards.

The project is built iteratively: starting from a minimal report and
evolving through Power Query ingestion, star schema modelling, advanced
DAX, and a Microsoft Fabric pipeline.

## Status
Phase 1 (in progress): minimal report on ongoing and completed waits.

## Data Source
Public Health Scotland, Scottish Health and Social Care Open Data
(opendata.nhs.scot), Stage of Treatment Waiting Times.
Licensed under the Open Government Licence v3.0.

## Repository Structure
- `powerbi/` Power BI project (PBIP format)
- `docs/` design decisions and documentation
- `data/` local data (not committed, data is loaded from source URLs)