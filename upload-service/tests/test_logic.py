from app.logic import MAX_BYTES, detect_type, media_type_for


def test_detects_pdf():
    assert detect_type(b"%PDF-1.7 rest of file") == "pdf"


def test_detects_png():
    assert detect_type(b"\x89PNG\r\n\x1a\n" + b"data") == "png"


def test_detects_jpeg():
    assert detect_type(b"\xff\xd8\xff\xe0 data") == "jpg"


def test_rejects_executable():
    assert detect_type(b"MZ\x90\x00 this is an exe") is None


def test_rejects_text_renamed_to_pdf():
    assert detect_type(b"just some text") is None


def test_limit_is_two_megabytes():
    assert MAX_BYTES == 2 * 1024 * 1024


def test_media_types():
    assert media_type_for("abc123.pdf") == "application/pdf"
    assert media_type_for("abc123.png") == "image/png"
    assert media_type_for("abc123.bin") == "application/octet-stream"