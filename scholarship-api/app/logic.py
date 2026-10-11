from datetime import date

MIN_GWA, MAX_GWA = 1.0, 5.0   # 1.00 is best, 5.00 is failing

def check_eligibility(s: dict, gwa: float, income: float, year_level: int,
                        today: date | None = None) -> dict:
    today = today or date.today()

    # Reject impossible input first (also catches NaN, since comparisons with NaN are False)
    if not (MIN_GWA <= gwa <= MAX_GWA):
        return {"eligible": False,
                "reasons": [f"GWA must be between {MIN_GWA:.2f} and {MAX_GWA:.2f}"]}
    if income < 0:
        return {"eligible": False, "reasons": ["Family income cannot be negative"]}

    reasons = []
    if not s["is_open"]:
        reasons.append("Scholarship is closed")
    if s.get("slots_remaining") is not None and s["slots_remaining"] <= 0:
        reasons.append("No slots remaining")
    if today > s["deadline"]:
        reasons.append("Deadline has passed")
    if gwa > s["max_gwa"]:
        reasons.append(f"GWA must be {s['max_gwa']} or better")
    if income > s["max_income"]:
        reasons.append(f"Family income must not exceed {s['max_income']}")
    if year_level not in s["year_levels"]:
        reasons.append("Year level not covered by this scholarship")
    return {"eligible": not reasons, "reasons": reasons}