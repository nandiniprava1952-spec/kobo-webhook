# Kobo Facility CSV Sync Webhook

Keeps `facility_master_redesigned.csv` (your form's own pulldata() media
file) up to date automatically whenever an enumerator submits the
autoclave checklist form -- so the next enumerator, on any device, sees
the latest counts pre-filled after their app syncs. Your form's XLSForm
and pulldata() formulas need NO changes for this approach.

## 1. Install

```bash
python -m venv venv
venv\Scripts\activate.bat        # Windows cmd
# or: source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

## 2. Configure

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Where to find it |
|---|---|---|
| `KOBO_API_TOKEN` | yes | Kobo -> Account Settings -> Security -> API Token |
| `MAIN_ASSET_UID` | yes | Open your **autoclave checklist form** (not a separate project) in Kobo; copy the code from its URL, e.g. `.../#/forms/aXXXXXXXXXXXXXXXXXXXXXX/` |
| `KOBO_BASE_URL` | no | Defaults to `https://kf.kobotoolbox.org` |
| `WEBHOOK_SHARED_SECRET` | recommended | Any random string you pick |
| `FORCE_REDEPLOY` | no | Leave `false` unless updates don't show up without it |

## 3. Seed the starting CSV

Copy your existing `facility_master_redesigned.csv` into this folder
(same name as `CSV_FILENAME_ON_KOBO` in `.env`). The webhook reads and
updates this file locally, then re-uploads it to Kobo after each change.

## 4. Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Check `http://localhost:8000/healthz` -> `{"status":"ok"}`.

## 5. Deploy somewhere with a public HTTPS URL

Kobo's REST Service needs to reach this over the internet -- `localhost`
won't work. Render, Railway, Fly.io, or any small VPS all work fine for
this low-traffic use.

**Important:** wherever you deploy, make sure `CSV_PATH` points to
**persistent storage** (a real disk, not an ephemeral container
filesystem that resets on every restart/redeploy) -- otherwise your CSV
updates will be lost each time the service restarts.

## 6. Point Kobo at it

In your autoclave form's project: **Settings -> REST Services -> Add a
service**
- Endpoint URL: `https://<your-host>/webhook/kobo`
- Custom header: `X-Webhook-Secret: <same value as WEBHOOK_SHARED_SECRET>`

That's it -- no Dynamic Data Attachment, no separate master project, no
`xml-external` changes to your form needed.

## How it works

1. Enumerator submits the form.
2. Kobo POSTs the submission JSON to `/webhook/kobo`.
3. `field_map.py` picks out the equipment-count fields relevant to
   whichever department was visited.
4. `csv_store.py` merges those into the matching facility's row in the
   local CSV (creating the row if it's a new facility).
5. The updated CSV is re-uploaded to Kobo via the Files API, replacing
   the old version under the same filename.
6. Any device that syncs afterward downloads the refreshed CSV, and
   `pulldata()` picks up the new values -- no form redesign or redeploy
   required in most cases.

## Notes

- `field_map.py` only writes fields for the department actually visited,
  so a sterilization-only visit won't blank out SNCU/OT numbers.
- If pulldata() values don't seem to update on devices after a sync, try
  setting `FORCE_REDEPLOY=true` in `.env` -- some Kobo versions need an
  explicit redeploy to notice media file content changes.
