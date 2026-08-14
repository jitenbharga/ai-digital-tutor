"""M-6: magic-byte validation for the vision-endpoint image uploads."""
from adaptive.core.user_materials import is_supported_image

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 20
WEBP = b"RIFF" + b"\x24\x00\x00\x00" + b"WEBP" + b"VP8 "
HEIC = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 16


def test_supported_images_accepted():
    assert is_supported_image(PNG)
    assert is_supported_image(JPEG)
    assert is_supported_image(WEBP)
    assert is_supported_image(HEIC)


def test_non_images_rejected():
    assert not is_supported_image(b"%PDF-1.7 pretending to be an image" + b"\x00" * 20)
    assert not is_supported_image(b"GIF89a" + b"\x00" * 20)          # GIF unsupported
    assert not is_supported_image(bytes(range(24)))                  # binary garbage
    assert not is_supported_image(b"")                               # empty
    assert not is_supported_image(b"short")                          # too small


def test_riff_that_is_not_webp_rejected():
    # A WAV file starts with RIFF but is not an image — must be rejected.
    wav = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVEfmt "
    assert not is_supported_image(wav)
