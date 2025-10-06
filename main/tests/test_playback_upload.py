"""
Tests upload behavior of /playback endpoint.

Reasoning:
- Only one file should be uploaded at once.
- Must reject unsupported file types.
- Accept only .mseed / .miniseed.
"""
import io
import pytest

def test_reject_multiple_files(client):
    data = {
        "seedlink_file": [
            (io.BytesIO(b"fake1"), "a.mseed"),
            (io.BytesIO(b"fake2"), "b.mseed"),
        ]
    }
    res = client.post("/playback", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert b"one file" in res.data.lower()

@pytest.mark.parametrize("bad_name", ["bad.txt", "test.sac", "x.bin"])
def test_reject_non_miniseed(client, bad_name):
    data = {"seedlink_file": (io.BytesIO(b"abc"), bad_name)}
    res = client.post("/playback", data=data, content_type="multipart/form-data")
    assert res.status_code in (400, 415)

@pytest.mark.parametrize("good_name", ["data.mseed", "trace.miniseed", "TRACE.MSEED"])
def test_accept_valid_miniseed(client, good_name):
    data = {"seedlink_file": (io.BytesIO(b"ok"), good_name)}
    res = client.post("/playback", data=data, content_type="multipart/form-data")
    assert res.status_code in (200, 202)
