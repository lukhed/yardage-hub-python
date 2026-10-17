# yardage-hub-python

A Python client for [yardage-hub](https://lukeheide.com/sports/yardage-hub), an open,
crowdsourced database of golf courses: where they are, and their scorecards (holes, par,
handicaps, tees, ratings, slopes, yardages). It starts from OpenStreetMap, and golfers fill in
the rest.

This README is a quick start. The full API documentation is at
**[lukeheide.com/sports/yardage-hub/docs](https://lukeheide.com/sports/yardage-hub/docs)**.

## Install

```bash
pip install yardage-hub
```

Python 3.9+, no dependencies.

## Get a key

Every call needs a key. Sign in at [lukeheide.com](https://lukeheide.com), open your profile
page, and generate one. It's shown once, so copy it somewhere safe; if you lose it, regenerate it.
Free keys allow 1,000 calls a day and 30 a minute.

```python
from yardage_hub import YardageHub

hub = YardageHub("yh_...")   # or set YARDAGE_HUB_KEY and call YardageHub()
```

## Quick start

```python
# Find a course
found = hub.search_courses("pebble beach", state="CA")
course = hub.get_course(found["courses"][0]["id"])

print(course["course_name"], course["par"])
for tee in course["tee_sets"]:
    print(tee["tee_name"], tee["yardage"], [(r["gender"], r["course_rating"], r["slope"]) for r in tee["ratings"]])
for hole in course["holes_data"]:
    print(hole["number"], hole["par"], hole["handicap_index"], hole["yardages"])

# Courses near a point (km)
near = hub.search_courses(lat=42.28, lon=-83.74, radius_km=10)

# Courses that need help from contributors near you
help = hub.courses_needing_help(lat=42.28, lon=-83.74, radius_km=25)
for c in help["courses"]:
    print(c["course_name"], [n["need"] for n in c["needs"]])
```

Name search forgives abbreviations, punctuation, and typos: "st johns", "mt pleasant", and
"pebel beach" all find what you mean.

## Methods

| Method | What it does |
|---|---|
| `search_courses(q, state, lat, lon, radius_km, kinds, page, page_size)` | Search by name, state, or distance. `kinds` defaults to `["course", "par3"]`; also `practice`, `disc`, `mini` |
| `get_course(course_id)` | One course: holes, tees and ratings, links, completeness. `None` for an unknown id |
| `course_edits(course_id, page_size, contributor_ref)` | A course's edit history, newest first |
| `courses_needing_help(state, lat, lon, radius_km, needs, page, page_size)` | Courses missing something a contributor can add, by state or near a point |
| `submit_edit(course_id, payload, note, evidence_url, contributor_ref, contributor_name)` | Propose a change (contact details, holes, tees, ratings, yardages, scorecard link) |
| `vote_edit(edit_id, vote, reason, contributor_ref, contributor_name)` | Back (`1`) or doubt (`-1`) a pending edit, or remove your vote (`0`) |
| `report_link(course_id, field, url, works, contributor_ref, contributor_name)` | Confirm a `website` or `scorecard_url` works, or report it dead |
| `report_course(course_id, kind, note, evidence_url, contributor_ref, contributor_name)` | Report a scorecard as `scorecard_changed`, `numbers_wrong`, or `other` |
| `submit_scorecard_photos(course_id, photos, note, replaces_link, contributor_ref, contributor_name)` | Send 1–4 photos of a course's scorecard; once approved they become its `scorecard_url` |

Each method returns the API's JSON as Python dicts and lists. The fields are described in the
[docs](https://lukeheide.com/sports/yardage-hub/docs).

## Writing: apply for write access

Every key can read. The last five methods send data to a review queue, and a person reviews
every edit, so they need a key with **write access**. New keys don't have it; a key without it
gets a 403.

1. **Contribute on the site first.** Suggest edits on course pages at
   [lukeheide.com/sports/yardage-hub](https://lukeheide.com/sports/yardage-hub).
2. **Once 5 of your edits are approved**, apply on your profile page. Say what you'll write, e.g.
   "building an app that lets people suggest edits".
3. **The maintainer reviews the application.** Once it's granted, your key can call the write
   methods.

Write access can be taken back. After a denial or revocation, you can apply again in 30 days.

An edit looks like this:

```python
hub.submit_edit(course_id, {
    "course": {"phone": "(415) 561-4661", "scorecard_url": "https://example.com/scorecard.pdf"},
    "holes": [{"number": 1, "par": 4, "handicap": 7}],
    "tees": [{"name": "Blue", "color": "blue", "gender": "M", "rating": 70.8, "slope": 132,
              "yardages": {"1": 512, "2": 410}}],
}, note="From the 2026 scorecard")
```

It's validated right away (a bad payload raises a 400) and waits as `pending` until it's
reviewed.

### Scorecard photos

Send 1–4 photos of a course's card, in order (front, back, …). Each one can be a file path,
`bytes`, or a binary file object:

```python
result = hub.submit_scorecard_photos(course_id, ["front.jpg", "back.jpg"],
                                     note="Card from the pro shop", contributor_ref="user-42")
result["url"]  # the photos; it becomes the course's scorecard_url once approved
```

Photos stay **private until a reviewer approves them**: until then `url` returns 404, for you too.

- **A photo is the card.** If the course already has a `scorecard_url`, the call is refused
  (409) unless you pass `replaces_link=True`. Pass it only when the user says the current link
  is wrong.
- **JPEG, PNG, or WebP, at most 2 MB each, and at least 1000 px on the long side** (500 on the
  short). Photos straight off a phone are 2–6 MB, so resize first: about 2400 px on the long
  side, JPEG quality 85. With Pillow:

  ```python
  from io import BytesIO
  from PIL import Image, ImageOps

  img = ImageOps.exif_transpose(Image.open("card.jpg")).convert("RGB")
  img.thumbnail((2400, 2400))
  buf = BytesIO()
  img.save(buf, "JPEG", quality=85)
  hub.submit_scorecard_photos(course_id, buf.getvalue(), contributor_ref="user-42")
  ```
- **Metadata is removed** on the server, including GPS location and orientation, so send photos
  upright (`exif_transpose` above does that).
- **Limits:** 5 photos per user a day, 200 per app, 500 in all (UTC days). An upload counts as
  two calls against your daily quota. App keys must pass `contributor_ref`, since the per-user
  limit counts by it.
- **Don't send cards with personal information** written on them (names, scores, handicaps).
  Approved photos are public.
- **Junk is deleted.** Photos that aren't a scorecard, can't be read, or show personal details are
  rejected as junk and deleted within the hour. After 3 in 30 days, that user's photo uploads
  are paused (403, saying until when). Links still work.

## Errors

A failed call raises `YardageHubError`, with `status`, `message`, and `retry_after` (seconds,
after a 429):

```python
from yardage_hub import YardageHubError

try:
    hub.submit_edit(course_id, {"course": {"phone": "555-0100"}})
except YardageHubError as e:
    if e.status == 403:
        print("This key is read-only: apply for write access on your profile page")
    elif e.status == 429:
        print(f"Over a limit; retry in {e.retry_after} s")
    else:
        raise
```

| Status | Meaning |
|---|---|
| 400 | Invalid input; the message says what |
| 401 | Missing, wrong, or revoked key |
| 403 | A read-only key tried to write, or this user's photo uploads are paused for junk |
| 404 | Unknown course or edit |
| 409 | Scorecard photos for a course that already has a scorecard link (pass `replaces_link=True`), or a photo already sent |
| 413 | A scorecard photo over 2 MB |
| 415 | A scorecard photo that isn't a JPEG, PNG, or WebP |
| 422 | A scorecard photo too small to read (under 1000 px on the long side or 500 on the short) |
| 429 | Over the daily or per-minute limit, or a scorecard photo limit |
| 503 | Scorecard photo storage is nearly full; uploads are paused |

## Data and license

The data contains information from OpenStreetMap, © OpenStreetMap contributors, and is available
under the [ODbL](https://opendatacommons.org/licenses/odbl/1-0/). Credit it wherever you show
it: "© OpenStreetMap contributors, yardage-hub". For the whole dataset, download the weekly
snapshots from [lukhed/yardage-hub-data](https://github.com/lukhed/yardage-hub-data); please
don't harvest it through the API.

This client is MIT licensed.
