import io
import shutil

import pytest
from PIL import Image

from us_mediakit.core.pipeline import ThumbnailRequest, generate_thumbnail
from us_mediakit.metadata.exiftool_client import ExifToolClient
from us_mediakit.metadata.gps import strip_gps
from us_mediakit.metadata.read import read_metadata
from us_mediakit.metadata.write import copy_metadata_from, write_tags

requires_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="exiftool nicht installiert"
)


def _jpeg_bytes(w: int = 200, h: int = 100) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 90, 160)).save(buf, format="JPEG")
    return buf.getvalue()


@requires_exiftool
def test_read_metadata_basic_fields():
    tags = read_metadata(_jpeg_bytes())
    assert tags["File:MIMEType"] == "image/jpeg"


@requires_exiftool
def test_write_and_read_roundtrip():
    written = write_tags(_jpeg_bytes(), {"IPTC:ObjectName": "Testbild"})
    tags = read_metadata(written)
    assert tags["IPTC:ObjectName"] == "Testbild"


@requires_exiftool
def test_copy_metadata_from_transfers_tags():
    source = write_tags(_jpeg_bytes(), {"IPTC:ObjectName": "Original-Titel"})
    target = _jpeg_bytes(50, 50)  # simuliert eine erzeugte Bildvariante ohne Metadaten

    merged = copy_metadata_from(source, target)

    tags = read_metadata(merged)
    assert tags["IPTC:ObjectName"] == "Original-Titel"
    with Image.open(io.BytesIO(merged)) as img:
        assert img.size == (50, 50)  # Bilddaten des Ziels, nur Metadaten kommen von der Quelle


@requires_exiftool
def test_strip_gps_removes_location_but_keeps_other_tags():
    with_location = write_tags(
        _jpeg_bytes(),
        {
            "GPSLatitude": "48.1234",
            "GPSLatitudeRef": "N",
            "GPSLongitude": "11.5678",
            "GPSLongitudeRef": "E",
            "IPTC:ObjectName": "Bild mit Standort",
        },
    )
    before = read_metadata(with_location)
    assert "EXIF:GPSLatitude" in before

    stripped = strip_gps(with_location)
    after = read_metadata(stripped)

    assert "EXIF:GPSLatitude" not in after
    assert "EXIF:GPSLongitude" not in after
    assert after["IPTC:ObjectName"] == "Bild mit Standort"


@requires_exiftool
def test_exiftool_client_reused_across_calls():
    with ExifToolClient() as client:
        tags_a = read_metadata(_jpeg_bytes(100, 100), client=client)
        tags_b = read_metadata(_jpeg_bytes(200, 200), client=client)
    assert tags_a["File:ImageWidth"] == 100
    assert tags_b["File:ImageWidth"] == 200


@requires_exiftool
def test_pipeline_carries_metadata_by_default():
    source = write_tags(_jpeg_bytes(400, 300), {"IPTC:ObjectName": "Pipeline-Test"})
    request = ThumbnailRequest(source=source, mode={"w": 100, "h": 100, "fit": "full"})

    result = generate_thumbnail(request)

    tags = read_metadata(result.data)
    assert tags["IPTC:ObjectName"] == "Pipeline-Test"


@requires_exiftool
def test_pipeline_strip_gps_removes_location_from_output():
    source = write_tags(
        _jpeg_bytes(400, 300),
        {
            "GPSLatitude": "48.1234",
            "GPSLatitudeRef": "N",
            "GPSLongitude": "11.5678",
            "GPSLongitudeRef": "E",
        },
    )
    request = ThumbnailRequest(
        source=source, mode={"w": 100, "h": 100, "fit": "full"}, strip_gps=True
    )

    result = generate_thumbnail(request)

    tags = read_metadata(result.data)
    assert "EXIF:GPSLatitude" not in tags


@requires_exiftool
def test_pipeline_no_carry_metadata_opt_out():
    source = write_tags(_jpeg_bytes(400, 300), {"IPTC:ObjectName": "Sollte nicht ankommen"})
    request = ThumbnailRequest(
        source=source, mode={"w": 100, "h": 100, "fit": "full"}, carry_metadata=False
    )

    result = generate_thumbnail(request)

    tags = read_metadata(result.data)
    assert "IPTC:ObjectName" not in tags
