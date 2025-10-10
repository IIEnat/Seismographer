"""
Upload behavior of /playback.

Policy (current server behavior):
- Exactly one file → enforced (400 if multiple).
- Accept only .miniseed (case-insensitive) → 200/202.
- Everything else (.mseed, .txt, .sac, etc.) → 400/415.
"""
import io
import pytest

def test_reject_multiple_files(client):
    data = {
        "seedlink_file": [
            (io.BytesIO(b"fake1"), "a.miniseed"),
            (io.BytesIO(b"fake2"), "b.miniseed"),
        ]
    }
    res = client.post("/playback", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert b"one file" in res.data.lower()

# anything not .miniseed should be rejected
@pytest.mark.parametrize("bad_name", ["bad.txt", "test.sac", "x.bin", "data.mseed", "TRACE.MSEED"])
def test_reject_non_miniseed(client, bad_name):
    res = client.post(
        "/playback",
        data={"seedlink_file": (io.BytesIO(b"abc"), bad_name)},
        content_type="multipart/form-data",
    )
    assert res.status_code in (400, 415)

# only .miniseed (case-insensitive) should be accepted
@pytest.mark.parametrize("good_name", ["trace.miniseed", "TRACE.MINISEED"])
def test_accept_only_miniseed(client, good_name):
    res = client.post(
        "/playback",
        data={"seedlink_file": (io.BytesIO(b"ok"), good_name)},
        content_type="multipart/form-data",
    )
    assert res.status_code in (200, 202)
