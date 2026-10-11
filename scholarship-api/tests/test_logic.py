from datetime import date
from app.logic import check_eligibility

S = {"is_open": True, "deadline": date(2099, 1, 1), "max_gwa": 2.0,
        "max_income": 250000, "year_levels": [2, 3, 4]}


def test_eligible():
    assert check_eligibility(S, 1.75, 100000, 3)["eligible"]


def test_gwa_too_low():
    r = check_eligibility(S, 2.5, 100000, 3)
    assert not r["eligible"] and any("GWA" in x for x in r["reasons"])


def test_income_too_high():
    assert not check_eligibility(S, 1.5, 400000, 3)["eligible"]


def test_wrong_year_level():
    assert not check_eligibility(S, 1.5, 100000, 1)["eligible"]


def test_deadline_passed():
    assert not check_eligibility(S, 1.5, 100000, 3, today=date(2100, 1, 1))["eligible"]


def test_zero_gwa_rejected():
    r = check_eligibility(S, 0, 100000, 3)
    assert not r["eligible"] and any("between" in x for x in r["reasons"])

def test_negative_gwa_rejected():
    assert not check_eligibility(S, -1.5, 100000, 3)["eligible"]

def test_gwa_above_five_rejected():
    assert not check_eligibility(S, 5.5, 100000, 3)["eligible"]

def test_negative_income_rejected():
    assert not check_eligibility(S, 1.5, -1, 3)["eligible"]


def test_full_scholarship_rejected():
    r = check_eligibility({**S, "slots_remaining": 0}, 1.5, 100000, 3)
    assert not r["eligible"] and "No slots remaining" in r["reasons"]

def test_scholarship_with_slots_is_eligible():
    assert check_eligibility({**S, "slots_remaining": 2}, 1.5, 100000, 3)["eligible"]