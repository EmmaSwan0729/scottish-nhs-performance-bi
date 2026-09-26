"""
Download NHS Scotland open data from Public Health Scotland (PHS) and land
the raw files in a bronze layer.

Why this exists:
    PHS open data rejects requests coming from Power BI Service cloud
    servers, so data is ingested here and Power BI reads it from the
    bronze layer instead.

How it works:
    1. For each resource ID, call the CKAN API (resource_show) to get the
       current download URL. The resource ID never changes, even when the
       file name does (e.g. ..._mar26.csv -> ..._jun26.csv).
    2. Download the raw CSV.
    3. Write it to the bronze layer at a fixed path per table:
         data/bronze/<table>/<table>.csv
       plus a manifest (data/bronze/_manifest.json) recording which source
       file each table came from and when it was loaded.

Targets:
    local (default)  writes into the repository. Once committed and pushed,
                     Git history acts as the versioned snapshot history and
                     Power BI reads the files from GitHub.
    adls             writes to Azure Data Lake Storage Gen2 (container
                     "bronze"), for when an Azure subscription is available.
                     Requires: az login, AZURE_STORAGE_ACCOUNT env var.

Usage (from the repository root):
    python ingestion/download_phs_data.py
    python ingestion/download_phs_data.py --target adls
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

CKAN_RESOURCE_SHOW = "https://www.opendata.nhs.scot/api/3/action/resource_show"
REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_BRONZE = REPO_ROOT / "data" / "bronze"
ADLS_CONTAINER = "bronze"

# The PHS site drops connections from clients that don't look like a browser.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/csv, */*",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# table name in the bronze layer -> PHS resource ID
RESOURCES = {
    "ongoing_waits": "5816ec92-66bf-4033-ae55-9df45ff19d49",
    "completed_waits": "4c091d26-1492-41e5-9577-832cbc1cd4cf",
    "health_board_labels": "652ff726-e676-4a20-abda-435b98dd7bdc",
    "country_labels": "9c6e6c56-2697-4184-92c6-60d69c2b6792",
    "special_health_board_labels": "0450a5a2-f600-4569-a9ae-5d6317141899",
    "specialty_labels": "6f2e3da0-b1b5-46cc-ac04-78495daedfa3",
}


def get_resource_metadata(resource_id: str) -> dict:
    """Look up a PHS resource via the CKAN API (current URL, last modified, ...)."""
    response = SESSION.get(CKAN_RESOURCE_SHOW, params={"id": resource_id}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"CKAN API returned an error for resource {resource_id}")
    return payload["result"]


def download(url: str) -> bytes:
    response = SESSION.get(url, timeout=300)
    response.raise_for_status()
    return response.content


class LocalWriter:
    def write(self, path: str, data: bytes) -> None:
        target = LOCAL_BRONZE / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


class AdlsWriter:
    def __init__(self) -> None:
        # imported here so the local target doesn't need the Azure packages
        from azure.identity import DefaultAzureCredential
        from azure.storage.filedatalake import DataLakeServiceClient

        account = os.environ.get("AZURE_STORAGE_ACCOUNT")
        if not account:
            sys.exit("Please set the AZURE_STORAGE_ACCOUNT environment variable.")
        service = DataLakeServiceClient(
            account_url=f"https://{account}.dfs.core.windows.net",
            credential=DefaultAzureCredential(),
        )
        self.file_system = service.get_file_system_client(ADLS_CONTAINER)

    def write(self, path: str, data: bytes) -> None:
        self.file_system.get_file_client(path).upload_data(data, overwrite=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PHS open data into the bronze layer.")
    parser.add_argument("--target", choices=["local", "adls"], default="local")
    args = parser.parse_args()

    writer = LocalWriter() if args.target == "local" else AdlsWriter()
    loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    manifest = {"loaded_at_utc": loaded_at, "tables": {}}
    failures = []

    for table, resource_id in RESOURCES.items():
        try:
            metadata = get_resource_metadata(resource_id)
            url = metadata["url"]
            source_file_name = url.rsplit("/", 1)[-1]
            content = download(url)

            writer.write(f"{table}/{table}.csv", content)

            manifest["tables"][table] = {
                "resource_id": resource_id,
                "source_file_name": source_file_name,
                "source_last_modified": metadata.get("last_modified"),
                "size_bytes": len(content),
            }
            print(f"[OK]   {table:<28} {source_file_name} ({len(content) / 1024:,.0f} KB)")
        except Exception as error:  # keep going so one bad resource doesn't stop the run
            failures.append(table)
            print(f"[FAIL] {table:<28} {error}")

    if manifest["tables"]:
        if manifest["tables"]:
            writer.write("_manifest.json", json.dumps(manifest, indent=2).encode("utf-8"))

    if failures:
        sys.exit(f"{len(failures)} table(s) failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()