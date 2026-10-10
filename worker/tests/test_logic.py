import json
import pytest
from app.logic import BadJob, MESSAGES, build_message, parse_job


def job(**overrides):
    data = {"application_id": 1, "user_id": 2, "status": "approved"}
    data.update(overrides)
    return json.dumps(data)


def test_every_status_has_a_message():
    for status in MESSAGES:
        assert build_message(status)


def test_unknown_status_gets_fallback_message():
    assert "weird" in build_message("weird")


def test_valid_job_is_parsed():
    assert parse_job(job())["status"] == "approved"


def test_invalid_json_is_rejected():
    with pytest.raises(BadJob):
        parse_job("garbage")


def test_missing_field_is_rejected():
    with pytest.raises(BadJob):
        parse_job(json.dumps({"application_id": 1, "status": "approved"}))


def test_unknown_status_is_rejected():
    with pytest.raises(BadJob):
        parse_job(job(status="exploded"))


def test_non_integer_ids_are_rejected():
    with pytest.raises(BadJob):
        parse_job(job(user_id="abc"))