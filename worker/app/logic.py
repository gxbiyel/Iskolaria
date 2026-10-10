import json

MESSAGES = {
    "submitted": "Application received.",
    "under_review": "Your application is now under review.",
    "approved": "Congratulations! Your application was approved.",
    "rejected": "Your application was not approved.",
    "waitlisted": "Your application has been waitlisted.",
    "cancelled": "Your application was cancelled.",
    "removed": "You have been removed from this scholarship.",
}


class BadJob(ValueError):
    """Raised when a queue message cannot be turned into a valid job."""


def build_message(status: str) -> str:
    return MESSAGES.get(status, f"Status changed to {status}.")


def parse_job(raw: str) -> dict:
    """Validate a raw queue payload and return it as a dict, or raise BadJob."""
    try:
        job = json.loads(raw)
    except (TypeError, ValueError):
        raise BadJob("not valid JSON")
    if not isinstance(job, dict):
        raise BadJob("job must be a JSON object")
    for key in ("application_id", "user_id", "status"):
        if key not in job:
            raise BadJob(f"missing field: {key}")
    if not isinstance(job["application_id"], int) or not isinstance(job["user_id"], int):
        raise BadJob("application_id and user_id must be integers")
    if job["status"] not in MESSAGES:
        raise BadJob(f"unknown status: {job['status']}")
    return job