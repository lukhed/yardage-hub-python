"""The client builds the right request for each route and turns errors into YardageHubError.
No network: urlopen is replaced. `python -m unittest` from the repo root."""

import email
import email.policy
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from yardage_hub import YardageHub, YardageHubError, __version__  # noqa: E402

BASE = "https://yardage-hub.lukhed.workers.dev/v1"
ID = "3f2c9a1e-0000-4000-8000-000000000001"


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.reply = {"ok": True}

        def urlopen(req, timeout):
            self.sent.append(req)
            return Response(json.dumps(self.reply).encode())

        patcher = mock.patch("urllib.request.urlopen", urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.hub = YardageHub("yh_test")

    def last(self):
        req = self.sent[-1]
        body = json.loads(req.data) if req.data else None
        return req.get_method(), req.full_url, body

    def test_reads_are_gets_with_a_query_string(self):
        self.hub.search_courses("presidio", state="CA", kinds=["course", "par3"], page_size=5)
        self.assertEqual(self.last(), ("GET", f"{BASE}/courses?q=presidio&state=CA&kinds=course%2Cpar3&page_size=5", None))
        self.hub.get_course(ID)
        self.assertEqual(self.last()[:2], ("GET", f"{BASE}/courses/{ID}"))
        self.hub.course_edits(ID, page_size=10)
        self.assertEqual(self.last()[1], f"{BASE}/courses/{ID}/edits?page_size=10")
        self.hub.courses_needing_help(lat=42.28, lon=-83.74, radius_km=25, needs=["no_website"])
        self.assertEqual(self.last()[1], f"{BASE}/help?lat=42.28&lon=-83.74&radius_km=25&needs=no_website")
        self.hub.courses_needing_help()
        self.assertEqual(self.last()[1], f"{BASE}/help")

    def test_writes_post_json_without_unset_fields(self):
        self.hub.submit_edit(ID, {"course": {"phone": "555"}}, note="from the card")
        self.assertEqual(self.last(), ("POST", f"{BASE}/courses/{ID}/edits",
                                       {"payload": {"course": {"phone": "555"}}, "note": "from the card"}))
        self.hub.vote_edit(ID, 1)
        self.assertEqual(self.last(), ("POST", f"{BASE}/edits/{ID}/votes", {"vote": 1}))
        self.hub.report_link(ID, "website", "https://a.example/", False)
        self.assertEqual(self.last()[2], {"field": "website", "url": "https://a.example/", "works": False})
        self.hub.report_course(ID, "numbers_wrong", note="hole 4")
        self.assertEqual(self.last()[1:], (f"{BASE}/courses/{ID}/reports", {"kind": "numbers_wrong", "note": "hole 4"}))

    def test_scorecard_photos_are_multipart(self):
        self.reply = {"edit_id": ID, "status": "pending"}
        with tempfile.TemporaryDirectory() as d:
            back = Path(d) / "back.png"
            back.write_bytes(b"\x89PNG back")
            result = self.hub.submit_scorecard_photos(ID, [b"\xff\xd8 front", back], note="pro shop card",
                                                      replaces_link=True, contributor_ref="42")
        self.assertEqual(result, {"edit_id": ID, "status": "pending"})
        req = self.sent[-1]
        self.assertEqual((req.get_method(), req.full_url), ("POST", f"{BASE}/courses/{ID}/scorecard-photos"))
        self.assertEqual(req.get_header("X-yardage-key"), "yh_test")
        content_type = req.get_header("Content-type")
        self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
        message = email.message_from_bytes(f"Content-Type: {content_type}\r\n\r\n".encode() + req.data,
                                           policy=email.policy.HTTP)
        parts = [(p.get_param("name", header="content-disposition"), p.get_payload(decode=True))
                 for p in message.iter_parts()]
        self.assertEqual(parts, [("note", b"pro shop card"), ("replaces_link", b"true"), ("contributor_ref", b"42"),
                                 ("photos", b"\xff\xd8 front"), ("photos", b"\x89PNG back")])

    def test_one_photo_can_be_passed_alone(self):
        self.hub.submit_scorecard_photos(ID, io.BytesIO(b"\xff\xd8 card"))
        self.assertIn(b"\xff\xd8 card", self.sent[-1].data)
        self.assertIn(b'name="replaces_link"\r\n\r\nfalse', self.sent[-1].data)
        self.assertNotIn(b'name="note"', self.sent[-1].data)

    def test_every_call_carries_the_key_and_version(self):
        self.hub.get_course(ID)
        self.assertEqual(self.sent[-1].get_header("X-yardage-key"), "yh_test")
        self.assertEqual(self.sent[-1].get_header("User-agent"), f"yardage-hub-python/{__version__}")

    def test_returns_the_json(self):
        self.reply = {"total": 1, "courses": []}
        self.assertEqual(self.hub.search_courses("x"), {"total": 1, "courses": []})

    def test_unknown_course_is_none(self):
        self.reply = None
        self.assertIsNone(self.hub.get_course(ID))

    def test_errors_carry_status_message_and_retry_after(self):
        def refuse(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {"Retry-After": "30"},
                                         io.BytesIO(b'{"message": "daily quota used; resets at 00:00 UTC"}'))

        with mock.patch("urllib.request.urlopen", refuse):
            with self.assertRaises(YardageHubError) as e:
                self.hub.search_courses("x")
        self.assertEqual((e.exception.status, e.exception.retry_after), (429, 30))
        self.assertIn("daily quota", e.exception.message)

    def test_needs_a_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertRaises(ValueError, YardageHub)
        with mock.patch.dict("os.environ", {"YARDAGE_HUB_KEY": "yh_env"}):
            self.assertEqual(YardageHub().key, "yh_env")


if __name__ == "__main__":
    unittest.main()
