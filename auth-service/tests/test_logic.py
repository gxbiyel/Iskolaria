import time
import jwt
import pytest
from app import logic


def test_student_number_formats_match():
    assert logic.normalize_student_number("2021-00123 ") == "202100123"
    assert logic.normalize_student_number("2021 00123") == "202100123"


def test_password_hash_roundtrip():
    h = logic.hash_password("secret123")
    assert h != "secret123"
    assert logic.verify_password("secret123", h)
    assert not logic.verify_password("wrong", h)


def test_token_roundtrip():
    t = logic.make_token(7, "admin", "s")
    p = logic.decode_token(t, "s")
    assert p["sub"] == "7" and p["role"] == "admin"


def test_wrong_secret_rejected():
    with pytest.raises(jwt.PyJWTError):
        logic.decode_token(logic.make_token(1, "applicant", "a"), "b")


def test_expired_token_rejected():
    with pytest.raises(jwt.PyJWTError):
        logic.decode_token(logic.make_token(1, "applicant", "s", ttl=-10), "s")