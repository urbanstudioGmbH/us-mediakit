"""argparse-basierte CLI. Jeder Unterbefehl entspricht einer Library-/API-Operation."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from us_mediakit import config
from us_mediakit.core.pipeline import ThumbnailRequest, ThumbnailResult, generate_thumbnail
from us_mediakit.metadata.gps import strip_gps as strip_gps_tags
from us_mediakit.metadata.read import read_metadata
from us_mediakit.metadata.write import write_tags


def _describe_actual_size(result: ThumbnailResult) -> tuple[int, int] | None:
    if result.source_image_type == "svg":
        return None
    try:
        with Image.open(io.BytesIO(result.data)) as img:
            return img.size
    except UnidentifiedImageError:
        return None


def _cmd_thumbnail(args: argparse.Namespace) -> int:
    presets = config.load_imageformats()
    if args.mode not in presets:
        print(f"Unbekanntes Preset {args.mode!r}. Verfügbar: {', '.join(sorted(presets))}", file=sys.stderr)
        return 1

    source_path = Path(args.source)
    source_bytes = source_path.read_bytes()

    request = ThumbnailRequest(
        source=source_bytes,
        mode=presets[args.mode],
        output_format=args.format,
        crop=args.crop,
        aspect_ratio=args.aspect_ratio,
        zoom=args.zoom,
        is_video=args.video,
        is_pdf=args.pdf,
        pdf_page=args.pdf_page,
        carry_metadata=args.carry_metadata,
        strip_gps=args.strip_gps,
    )

    try:
        result = generate_thumbnail(request)
    except Exception as exc:  # noqa: BLE001 — CLI-Grenze: Fehler dem Nutzer verständlich melden
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"OK (dry-run): Zielgröße {result.target_width}x{result.target_height}")
        return 0

    actual_size = _describe_actual_size(result)
    note = ""
    if actual_size and actual_size != (result.target_width, result.target_height):
        note = (
            f" — tatsächlich {actual_size[0]}x{actual_size[1]}, kleiner als angefragt: "
            "Vergrößerung ohne --ai-Provider wird nicht durchgeführt, siehe Programmierplan"
        )

    if args.output:
        Path(args.output).write_bytes(result.data)
        print(f"Geschrieben: {args.output} (Ziel {result.target_width}x{result.target_height}){note}")
    else:
        sys.stdout.buffer.write(result.data)

    return 0


def _cmd_meta_read(args: argparse.Namespace) -> int:
    data = Path(args.source).read_bytes()
    try:
        tags = read_metadata(data)
    except Exception as exc:  # noqa: BLE001 — CLI-Grenze
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(tags, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_meta_write(args: argparse.Namespace) -> int:
    data = Path(args.source).read_bytes()
    tags: dict[str, str] = {}
    for assignment in args.set or []:
        if "=" not in assignment:
            print(f"Ungültiges --set {assignment!r}, erwarte FIELD=VALUE", file=sys.stderr)
            return 1
        key, value = assignment.split("=", 1)
        tags[key] = value

    try:
        result = write_tags(data, tags) if tags else data
        if args.strip_gps:
            result = strip_gps_tags(result)
    except Exception as exc:  # noqa: BLE001 — CLI-Grenze
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    Path(args.source).write_bytes(result)
    print(f"Geschrieben: {args.source}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="us-mediakit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    thumbnail = subparsers.add_parser("thumbnail", help="Zuschnitt/Resize gemäß Preset")
    thumbnail.add_argument("source")
    thumbnail.add_argument("--mode", required=True, help="Preset-Name aus imageformats.json")
    thumbnail.add_argument("--crop", choices=["crop", "greedycrop", "greedyscalecrop"])
    thumbnail.add_argument("--format", default="jpg")
    thumbnail.add_argument("--aspect-ratio", dest="aspect_ratio")
    thumbnail.add_argument("--zoom")
    thumbnail.add_argument("--video", action="store_true")
    thumbnail.add_argument("--pdf", action="store_true")
    thumbnail.add_argument("--pdf-page", type=int, default=1)
    thumbnail.add_argument("--dry-run", action="store_true")
    thumbnail.add_argument(
        "--no-carry-metadata", dest="carry_metadata", action="store_false", default=True
    )
    thumbnail.add_argument("--strip-gps", action="store_true")
    thumbnail.add_argument("-o", "--output")
    thumbnail.set_defaults(func=_cmd_thumbnail)

    meta = subparsers.add_parser("meta", help="Metadaten lesen/schreiben")
    meta_sub = meta.add_subparsers(dest="meta_command", required=True)

    meta_read = meta_sub.add_parser("read")
    meta_read.add_argument("source")
    meta_read.set_defaults(func=_cmd_meta_read)

    meta_write = meta_sub.add_parser("write")
    meta_write.add_argument("source")
    meta_write.add_argument("--set", action="append", metavar="FIELD=VALUE")
    meta_write.add_argument("--strip-gps", action="store_true")
    meta_write.set_defaults(func=_cmd_meta_write)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
