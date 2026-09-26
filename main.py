"""
KoboToolbox REST Service webhook -> facility_master_redesigned.csv sync

Purpose
-------
Your autoclave checklist form pulls equipment counts via pulldata() from
facility_master_redesigned.csv, uploaded as the form's own media file.
This service listens for new submissions (Kobo calls it via a REST
Service webhook), updates the matching facility's row in that CSV, and
re-uploads the CSV to Kobo -- so the next enumerator's device, after it
syncs, sees the latest counts pre-filled. No separate "master project" or
Dynamic Data Attachment needed -- your existing pulldata() formulas keep
working exactly as they are.

How Kobo calls this
--------------------
In your form's project: Settings -> REST Services -> Add a service
  - URL: https://<your-host>/webhook/kobo
  - Custom header: X-Webhook-Secret: <a random string>
    (set the same value in WEBHOOK_SHARED_SECRET below)
"""

import logging
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from field_map import build_master_update, find_field
from csv_store import (
    fetch_current_csv_from_kobo,
    load_rows_from_bytes,
    update_facility,
    save_rows,
    sync_csv_to_kobo,
    redeploy_form,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kobo_webhook")

# ---------------------------------------------------------------------------
# Configuration (set these in a .env file in this folder, or as real
# environment variables -- real env vars always take priority)
# ---------------------------------------------------------------------------
KOBO_BASE_URL = os.environ.get("KOBO_BASE_URL", "https://kf.kobotoolbox.org")
KOBO_API_TOKEN = os.environ["KOBO_API_TOKEN"]
MAIN_ASSET_UID = os.environ["MAIN_ASSET_UID"]  # the autoclave checklist form's own asset UID
WEBHOOK_SHARED_SECRET = os.environ.get("WEBHOOK_SHARED_SECRET")
FORCE_REDEPLOY = os.environ.get("FORCE_REDEPLOY", "false").lower() == "true"

HEADERS = {
    "Authorization": f"Token {KOBO_API_TOKEN}",
    "Accept": "application/json",
}

app = FastAPI(title="Kobo Facility CSV Sync")


@app.post("/webhook/kobo")
async def kobo_webhook(
    request: Request,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    if WEBHOOK_SHARED_SECRET and x_webhook_secret != WEBHOOK_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing webhook secret")

    submission = await request.json()

    facility_code = find_field(submission, "facility_name_select")
    if not facility_code:
        logger.warning("Submission missing facility_name_select, skipping: %s",
                        submission.get("_id"))
        return JSONResponse({"status": "skipped", "reason": "no facility_code"}, status_code=200)

    try:
        fields_to_write = build_master_update(submission)
    except ValueError as e:
        logger.warning("Could not map submission %s: %s", submission.get("_id"), e)
        return JSONResponse({"status": "skipped", "reason": str(e)}, status_code=200)

    if not fields_to_write:
        return JSONResponse({"status": "skipped", "reason": "no mappable fields"}, status_code=200)

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Fetch the CSV currently on Kobo (the real source of truth --
        #    don't trust local disk, which may reset on ephemeral hosts)
        current_bytes = await fetch_current_csv_from_kobo(client, KOBO_BASE_URL, MAIN_ASSET_UID, HEADERS)
        rows = load_rows_from_bytes(current_bytes) if current_bytes else {}

        # 2. Merge in this submission's updates, write to a local temp file
        rows = update_facility(facility_code, fields_to_write, rows)
        save_rows(rows)
        logger.info("Updated row for %s: %s", facility_code, fields_to_write)

        # 3. Push the merged CSV back to Kobo as the form's media file
        await sync_csv_to_kobo(client, KOBO_BASE_URL, MAIN_ASSET_UID, HEADERS)
        if FORCE_REDEPLOY:
            await redeploy_form(client, KOBO_BASE_URL, MAIN_ASSET_UID, HEADERS)

    return {"status": "ok", "facility_code": facility_code, "fields_updated": list(fields_to_write)}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}"""
KoboToolbox REST Service webhook -> facility_master_redesigned.csv sync

Purpose
-------
Your autoclave checklist form pulls equipment counts via pulldata() from
facility_master_redesigned.csv, uploaded as the form's own media file.
This service listens for new submissions (Kobo calls it via a REST
Service webhook), updates the matching facility's row in that CSV, and
re-uploads the CSV to Kobo -- so the next enumerator's device, after it
syncs, sees the latest counts pre-filled. No separate "master project" or
Dynamic Data Attachment needed -- your existing pulldata() formulas keep
working exactly as they are.

How Kobo calls this
--------------------
In your form's project: Settings -> REST Services -> Add a service
  - URL: https://<your-host>/webhook/kobo
  - Custom header: X-Webhook-Secret: <a random string>
    (set the same value in WEBHOOK_SHARED_SECRET below)
"""

import logging
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from field_map import build_master_update
from csv_store import (
    fetch_current_csv_from_kobo,
    load_rows_from_bytes,
    update_facility,
    save_rows,
    sync_csv_to_kobo,
    redeploy_form,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kobo_webhook")

# ---------------------------------------------------------------------------
# Configuration (set these in a .env file in this folder, or as real
# environment variables -- real env vars always take priority)
# ---------------------------------------------------------------------------
KOBO_BASE_URL = os.environ.get("KOBO_BASE_URL", "https://kf.kobotoolbox.org")
KOBO_API_TOKEN = os.environ["KOBO_API_TOKEN"]
MAIN_ASSET_UID = os.environ["MAIN_ASSET_UID"]  # the autoclave checklist form's own asset UID
WEBHOOK_SHARED_SECRET = os.environ.get("WEBHOOK_SHARED_SECRET")
FORCE_REDEPLOY = os.environ.get("FORCE_REDEPLOY", "false").lower() == "true"

HEADERS = {
    "Authorization": f"Token {KOBO_API_TOKEN}",
    "Accept": "application/json",
}

app = FastAPI(title="Kobo Facility CSV Sync")


@app.post("/webhook/kobo")
async def kobo_webhook(
    request: Request,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    if WEBHOOK_SHARED_SECRET and x_webhook_secret != WEBHOOK_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing webhook secret")

    submission = await request.json()

    facility_code = submission.get("facility_name_select")
    if not facility_code:
        logger.warning("Submission missing facility_name_select, skipping: %s",
                        submission.get("_id"))
        return JSONResponse({"status": "skipped", "reason": "no facility_code"}, status_code=200)

    try:
        fields_to_write = build_master_update(submission)
    except ValueError as e:
        logger.warning("Could not map submission %s: %s", submission.get("_id"), e)
        return JSONResponse({"status": "skipped", "reason": str(e)}, status_code=200)

    if not fields_to_write:
        return JSONResponse({"status": "skipped", "reason": "no mappable fields"}, status_code=200)

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Fetch the CSV currently on Kobo (the real source of truth --
        #    don't trust local disk, which may reset on ephemeral hosts)
        current_bytes = await fetch_current_csv_from_kobo(client, KOBO_BASE_URL, MAIN_ASSET_UID, HEADERS)
        rows = load_rows_from_bytes(current_bytes) if current_bytes else {}

        # 2. Merge in this submission's updates, write to a local temp file
        rows = update_facility(facility_code, fields_to_write, rows)
        save_rows(rows)
        logger.info("Updated row for %s: %s", facility_code, fields_to_write)

        # 3. Push the merged CSV back to Kobo as the form's media file
        await sync_csv_to_kobo(client, KOBO_BASE_URL, MAIN_ASSET_UID, HEADERS)
        if FORCE_REDEPLOY:
            await redeploy_form(client, KOBO_BASE_URL, MAIN_ASSET_UID, HEADERS)

    return {"status": "ok", "facility_code": facility_code, "fields_updated": list(fields_to_write)}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
