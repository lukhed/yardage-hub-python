"""A thin client for the yardage-hub public API: one method per route, returning the JSON."""

import json
import os
import uuid
import urllib.error
import urllib.parse
import urllib.request

from . import __version__

BASE_URL = "https://yardage-hub.lukhed.workers.dev/v1"
DOCS_URL = "https://lukeheide.com/sports/yardage-hub/docs"


class YardageHubError(Exception):
    """An error response from the API.

    `status` is the HTTP status (401 bad key, 403 read-only key, 404 unknown course, 429 over a
    limit, ...), `message` the API's explanation, and `retry_after` the seconds to wait after a 429.
    """

    def __init__(self, status, message, retry_after=None):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message
        self.retry_after = int(retry_after) if retry_after and str(retry_after).isdigit() else None


class YardageHub:
    """Calls the yardage-hub API with your key.

    `key` defaults to the YARDAGE_HUB_KEY environment variable. Get a key from your profile page at
    lukeheide.com.
    """

    def __init__(self, key=None, base_url=BASE_URL, timeout=30):
        self.key = key or os.environ.get("YARDAGE_HUB_KEY")
        if not self.key:
            raise ValueError(f"pass key= or set YARDAGE_HUB_KEY; get a key at {DOCS_URL}")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ── Reads ────────────────────────────────────────────────────────────────

    def search_courses(self, q=None, state=None, lat=None, lon=None, radius_km=None, kinds=None,
                       page=None, page_size=None):
        """Search courses by name, state, or distance. Give at least one of q, state, or lat and lon.
        Returns { total, page, page_size, courses }."""
        return self._get("/courses", q=q, state=state, lat=lat, lon=lon, radius_km=radius_km,
                         kinds=kinds, page=page, page_size=page_size)

    def get_course(self, course_id):
        """One course with its holes, tees, ratings, and links. None for an unknown id."""
        return self._get(f"/courses/{course_id}")

    def course_edits(self, course_id, page_size=None, contributor_ref=None):
        """A course's edit history, newest first."""
        return self._get(f"/courses/{course_id}/edits", page_size=page_size, contributor_ref=contributor_ref)

    def courses_needing_help(self, state=None, lat=None, lon=None, radius_km=None, needs=None,
                             page=None, page_size=None):
        """Courses where a contributor can help, by state or near a point. With no area, a sample.
        Returns { total, page, page_size, courses, counts } (or { sample, page_size, courses })."""
        return self._get("/help", state=state, lat=lat, lon=lon, radius_km=radius_km, needs=needs,
                         page=page, page_size=page_size)

    # ── Writes (need a key with write access) ────────────────────────────────

    def submit_edit(self, course_id, payload, note=None, evidence_url=None, contributor_ref=None,
                    contributor_name=None):
        """Propose a change to a course. It waits for review. Returns { id, status }."""
        return self._post(f"/courses/{course_id}/edits", payload=payload, note=note,
                          evidence_url=evidence_url, contributor_ref=contributor_ref,
                          contributor_name=contributor_name)

    def vote_edit(self, edit_id, vote, reason=None, contributor_ref=None, contributor_name=None):
        """Back (1) or doubt (-1) a pending edit, or remove your vote (0). Returns { up, down, my_vote }."""
        return self._post(f"/edits/{edit_id}/votes", vote=vote, reason=reason,
                          contributor_ref=contributor_ref, contributor_name=contributor_name)

    def report_link(self, course_id, field, url, works, contributor_ref=None, contributor_name=None):
        """Confirm a course link works or report it dead. `field` is "scorecard_url" or "website",
        and `url` its current value. Returns the link's status."""
        return self._post(f"/courses/{course_id}/link-reports", field=field, url=url, works=works,
                          contributor_ref=contributor_ref, contributor_name=contributor_name)

    def report_course(self, course_id, kind, note=None, evidence_url=None, contributor_ref=None,
                      contributor_name=None):
        """Report a course's scorecard as wrong or out of date. `kind` is "scorecard_changed",
        "numbers_wrong", or "other" (needs a note)."""
        return self._post(f"/courses/{course_id}/reports", kind=kind, note=note, evidence_url=evidence_url,
                          contributor_ref=contributor_ref, contributor_name=contributor_name)

    def submit_scorecard_photos(self, course_id, photos, note=None, replaces_link=False,
                                contributor_ref=None, contributor_name=None):
        """Send 1-4 photos of a course's scorecard, in order (front, back, ...). Once a reviewer
        approves, they become the course's scorecard_url.

        Each photo is a file path, bytes, or a binary file object: JPEG, PNG, or WebP, at most
        2 MB. Resize phone photos first (about 2400 px on the long side). Location and other
        metadata are removed on the server, so send them upright. If the course already has a
        scorecard_url, pass replaces_link=True only when the user says that link is wrong. App keys
        must pass contributor_ref. Returns { edit_id, status, submission_id, url, photos }.
        """
        if isinstance(photos, (str, bytes, os.PathLike)) or hasattr(photos, "read"):
            photos = [photos]
        files = [_read_photo(p) for p in photos]
        fields = {"note": note, "replaces_link": "true" if replaces_link else "false",
                  "contributor_ref": contributor_ref, "contributor_name": contributor_name}
        boundary = uuid.uuid4().hex
        crlf = b"\r\n"
        parts = []
        for name, value in fields.items():
            if value is not None:
                head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
                parts.append(head.encode() + str(value).encode() + crlf)
        for i, data in enumerate(files, 1):
            head = (f'--{boundary}\r\nContent-Disposition: form-data; name="photos"; filename="photo-{i}"\r\n'
                    'Content-Type: application/octet-stream\r\n\r\n')
            parts.append(head.encode() + data + crlf)
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(self.base_url + f"/courses/{course_id}/scorecard-photos", data=body,
                                     method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        return self._send(req)

    # ── HTTP ─────────────────────────────────────────────────────────────────

    def _get(self, path, **params):
        query = {k: ",".join(v) if isinstance(v, (list, tuple)) else v
                 for k, v in params.items() if v is not None}
        url = self.base_url + path + ("?" + urllib.parse.urlencode(query) if query else "")
        return self._send(urllib.request.Request(url, method="GET"))

    def _post(self, path, **fields):
        body = json.dumps({k: v for k, v in fields.items() if v is not None}).encode()
        req = urllib.request.Request(self.base_url + path, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        return self._send(req)

    def _send(self, req):
        req.add_header("x-yardage-key", self.key)
        req.add_header("User-Agent", f"yardage-hub-python/{__version__}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as e:
            try:
                message = json.loads(e.read() or b"{}").get("message") or e.reason
            except ValueError:
                message = e.reason
            raise YardageHubError(e.code, message, e.headers.get("Retry-After")) from None


def _read_photo(photo):
    """A photo's bytes, from bytes, a binary file object, or a path."""
    if isinstance(photo, bytes):
        return photo
    if hasattr(photo, "read"):
        return photo.read()
    with open(photo, "rb") as f:
        return f.read()
