from datetime import date


def check_eligibility(s: dict, gwa: float, income: float, year_level: int,
                        today: date | None = None) -> dict:
    today = today or date.today()
    reasons = []
    if not s["is_open"]:
        reasons.append("Scholarship is closed")
    if today > s["deadline"]:
        reasons.append("Deadline has passed")
    if gwa > s["max_gwa"]:
        reasons.append(f"GWA must be {s['max_gwa']} or better")
    if income > s["max_income"]:
        reasons.append(f"Family income must not exceed {s['max_income']}")
    if year_level not in s["year_levels"]:
        reasons.append("Year level not covered by this scholarship")
    return {"eligible": not reasons, "reasons": reasons}