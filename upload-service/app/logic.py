MAX_BYTES = 2 * 1024 * 1024  # 2 MB

# detected type -> extension used for the stored file
EXT = {"pdf": ".pdf", "jpg": ".jpg", "png": ".png"}

# stored extension -> content type sent on download
MEDIA_TYPES = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".png": "image/png"}


def detect_type(head: bytes):
    """Identify the file by its first bytes (signature), not by its filename.
    A renamed .exe will not pass this check."""
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    return None


def media_type_for(stored_name: str) -> str:
    for ext, media in MEDIA_TYPES.items():
        if stored_name.endswith(ext):
            return media
    return "application/octet-stream"