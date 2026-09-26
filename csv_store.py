"""
Maintains facility_master_redesigned.csv locally and pushes it to Kobo as
the main form's media file, so pulldata() calls on any device pick up the
latest values after their next sync.

Kobo's v2 API doesn't let you overwrite a media file in place -- you must
DELETE the existing file entry, then POST a new one with the same
filename. That's what sync_csv_to_kobo() does below.
"""

import csv
import io
import logging
import os

import httpx

logger = logging.getLogger("kobo_webhook.csv_store")

CSV_PATH = os.environ.get("CSV_PATH", "facility_master_redesigned.csv")
CSV_FILENAME_ON_KOBO = os.environ.get("CSV_FILENAME_ON_KOBO", "facility_master_redesigned.csv")
MASTER_KEY_FIELD = "facility_code"


async def fetch_current_csv_from_kobo(
    client: httpx.AsyncClient,
    kobo_base_url: str,
    main_asset_uid: str,
    headers: dict,
) -> bytes | None:
    """
    Download the CSV currently attached to the form on Kobo, so we always
    update the real, latest version rather than trusting local disk state
    (which may be wiped on restart on ephemeral hosts like Render's free
    tier). Returns None if no such file exists yet on Kobo.
    """
    files_url = f"{kobo_base_url}/api/v2/assets/{main_asset_uid}/files/"
    resp = await client.get(files_url, headers=headers)
    resp.raise_for_status()
    for entry in resp.json().get("results", []):
        if entry.get("metadata", {}).get("filename") == CSV_FILENAME_ON_KOBO:
            content_url = entry.get("content") or entry["url"]
            dl_resp = await client.get(content_url, headers=headers)
            dl_resp.raise_for_status()
            return dl_resp.content
    return None


def load_rows() -> dict[str, dict]:
    """Read the local CSV into {facility_code: {field: value, ...}}."""
    if not os.path.exists(CSV_PATH):
        return {}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row[MASTER_KEY_FIELD]: row for row in reader if row.get(MASTER_KEY_FIELD)}


def load_rows_from_bytes(csv_bytes: bytes) -> dict[str, dict]:
    """Same as load_rows(), but parses CSV content already in memory."""
    text = csv_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    return {row[MASTER_KEY_FIELD]: row for row in reader if row.get(MASTER_KEY_FIELD)}


def save_rows(rows: dict[str, dict]) -> None:
    """Write {facility_code: {...}} back out as CSV, unioning all columns seen."""
    fieldnames: list[str] = [MASTER_KEY_FIELD]
    for row in rows.values():
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows.values():
            writer.writerow(row)


def update_facility(facility_code: str, new_fields: dict, rows: dict[str, dict]) -> dict[str, dict]:
    """Merge new_fields into rows[facility_code] (creating it if needed). Returns the updated rows dict."""
    existing = rows.get(facility_code, {MASTER_KEY_FIELD: facility_code})
    existing.update(new_fields)
    existing[MASTER_KEY_FIELD] = facility_code
    rows[facility_code] = existing
    return rows


async def sync_csv_to_kobo(
    client: httpx.AsyncClient,
    kobo_base_url: str,
    main_asset_uid: str,
    headers: dict,
) -> None:
    """
    Push the local CSV to Kobo as the main form's media file, replacing any
    existing file with the same name. Does NOT redeploy the form -- per
    Kobo community reports, updated CSV media content is picked up by
    pulldata() on next device sync without a redeploy. If your Kobo
    instance behaves differently, call redeploy_form() below afterward.
    """
    files_url = f"{kobo_base_url}/api/v2/assets/{main_asset_uid}/files/"

    # Find and delete the existing file entry with the same filename, if any
    resp = await client.get(files_url, headers=headers)
    resp.raise_for_status()
    for entry in resp.json().get("results", []):
        metadata = entry.get("metadata", {})
        if metadata.get("filename") == CSV_FILENAME_ON_KOBO:
            delete_url = entry["url"]
            del_resp = await client.delete(delete_url, headers=headers)
            if del_resp.status_code not in (204, 404):
                del_resp.raise_for_status()
            logger.info("Deleted existing media file %s before re-upload", CSV_FILENAME_ON_KOBO)
            break

    # Upload the new version
    with open(CSV_PATH, "rb") as f:
        csv_bytes = f.read()

    data = {
        "description": "Facility master data (auto-synced)",
        "file_type": "form_media",
        "metadata": f'{{"filename": "{CSV_FILENAME_ON_KOBO}"}}',
    }
    upload_files = {"content": (CSV_FILENAME_ON_KOBO, io.BytesIO(csv_bytes), "text/csv")}

    resp = await client.post(files_url, headers=headers, data=data, files=upload_files)
    resp.raise_for_status()
    logger.info("Uploaded refreshed %s to Kobo", CSV_FILENAME_ON_KOBO)


async def redeploy_form(
    client: httpx.AsyncClient,
    kobo_base_url: str,
    main_asset_uid: str,
    headers: dict,
) -> None:
    """Optional: force a redeploy if your Kobo instance needs it for media changes to show up."""
    detail_url = f"{kobo_base_url}/api/v2/assets/{main_asset_uid}/.json"
    resp = await client.get(detail_url, headers=headers)
    resp.raise_for_status()
    version_id = resp.json().get("version_id")

    deploy_url = f"{kobo_base_url}/api/v2/assets/{main_asset_uid}/deployment/"
    resp = await client.patch(
        deploy_url, headers=headers, data={"active": "true", "version_id": version_id}
    )
    resp.raise_for_status()
    logger.info("Redeployed form (version_id=%s)", version_id)
