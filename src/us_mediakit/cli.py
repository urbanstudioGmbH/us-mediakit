"""argparse-basierte CLI. Jeder Unterbefehl entspricht einer Library-/API-Operation."""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from us_mediakit import config
from us_mediakit.c2pa.sign import SignerConfig, SignRequest
from us_mediakit.c2pa.sign import sign as c2pa_sign
from us_mediakit.c2pa.verify import verify as c2pa_verify
from us_mediakit.core.pipeline import ThumbnailRequest, ThumbnailResult, generate_thumbnail
from us_mediakit.media.video import DEFAULT_SEEK_SECONDS
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
    if args.mode:
        presets = config.load_imageformats()
        if args.mode not in presets:
            print(f"Unbekanntes Preset {args.mode!r}. Verfügbar: {', '.join(sorted(presets))}", file=sys.stderr)
            return 1
        thumbnail_mode = presets[args.mode]
    elif args.width and args.height:
        # Presets sind optional: ohne --mode reichen Zielmaße direkt aus, ohne dafür
        # vorher einen benannten Eintrag in imageformats.json anlegen zu müssen.
        thumbnail_mode = {"w": args.width, "h": args.height, "fit": args.fit}
    else:
        print("Entweder --mode oder --width zusammen mit --height angeben.", file=sys.stderr)
        return 1

    source_path = Path(args.source)
    source_bytes = source_path.read_bytes()

    signer_config = None
    if args.c2pa_cert and args.c2pa_key:
        signer_config = SignerConfig(
            sign_cert=Path(args.c2pa_cert).read_bytes(),
            private_key=Path(args.c2pa_key).read_bytes(),
        )

    c2pa_overrides: dict = {}
    if args.c2pa_json:
        c2pa_overrides = json.loads(Path(args.c2pa_json).read_text(encoding="utf-8"))

    request = ThumbnailRequest(
        source=source_bytes,
        mode=thumbnail_mode,
        output_format=args.format,
        crop=args.crop,
        aspect_ratio=args.aspect_ratio,
        alignx=args.align_x,
        aligny=args.align_y,
        zoom=args.zoom,
        max_upscale_factor=args.max_upscale_factor,
        is_video=args.video,
        video_seek_seconds=args.video_seek_seconds,
        is_pdf=args.pdf,
        pdf_page=args.pdf_page,
        carry_metadata=args.carry_metadata,
        strip_gps=args.strip_gps,
        carry_c2pa=args.carry_c2pa,
        c2pa_signer_config=signer_config,
        c2pa_digital_source_type=c2pa_overrides.get("digital_source_type"),
        c2pa_actions=c2pa_overrides.get("actions", []),
        c2pa_assertions=c2pa_overrides.get("assertions", []),
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
            "Vergrößerung ohne --ai-Provider wird nicht durchgeführt, siehe docs/fit-modes.md"
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


def _cmd_c2pa_verify(args: argparse.Namespace) -> int:
    data = Path(args.source).read_bytes()
    mime_type = args.mime_type or "image/jpeg"
    result = c2pa_verify(data, mime_type)

    if not result.has_manifest:
        print("Kein C2PA-Manifest gefunden.")
        return 1

    print(f"validation_state: {result.validation_state}")
    print(json.dumps(result.validation_results, indent=2, ensure_ascii=False))
    return 0 if result.validation_state == "Valid" else 1


def _cmd_c2pa_sign(args: argparse.Namespace) -> int:
    data = Path(args.source).read_bytes()
    mime_type = args.mime_type or "image/jpeg"

    signer_config = SignerConfig(
        sign_cert=Path(args.cert).read_bytes(),
        private_key=Path(args.key).read_bytes(),
    )

    extra_actions = []
    extra_assertions = []
    if args.actions_json:
        payload = json.loads(Path(args.actions_json).read_text(encoding="utf-8"))
        extra_actions = payload.get("actions", [])
        extra_assertions = payload.get("assertions", [])

    try:
        signed = c2pa_sign(
            SignRequest(
                data=data,
                mime_type=mime_type,
                signer_config=signer_config,
                digital_source_type=args.source_type,
                extra_actions=extra_actions,
                extra_assertions=extra_assertions,
            )
        )
    except Exception as exc:  # noqa: BLE001 — CLI-Grenze
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    Path(args.source).write_bytes(signed)
    print(f"Signiert: {args.source}")
    return 0


def _cmd_admin_api_key_create(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone

    from us_mediakit.api.deps import generate_api_key
    from us_mediakit.db.engine import create_db_engine, create_session_factory, init_db
    from us_mediakit.db.models import ApiKey

    engine = create_db_engine()
    init_db(engine)
    session_factory = create_session_factory(engine)

    generated = generate_api_key()
    with session_factory() as session:
        session.add(
            ApiKey(
                id=generated.key_prefix,
                account_ref=args.account_ref,
                key_prefix=generated.key_prefix,
                key_hash=generated.key_hash,
                label=args.label,
                status="active",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    print(f"API-Key erzeugt: {generated.raw_key}")
    print("Dieser Key wird nirgendwo gespeichert — jetzt sichern, er lässt sich nicht erneut anzeigen.")
    return 0


def _cmd_admin_api_key_suspend(args: argparse.Namespace) -> int:
    from us_mediakit.db.engine import create_db_engine, create_session_factory
    from us_mediakit.db.models import ApiKey

    session_factory = create_session_factory(create_db_engine())
    with session_factory() as session:
        api_key = session.get(ApiKey, args.key_id)
        if api_key is None:
            print(f"API-Key {args.key_id!r} nicht gefunden.", file=sys.stderr)
            return 1
        api_key.status = "suspended"
        session.commit()
    print(f"Gesperrt: {args.key_id}")
    return 0


def _cmd_admin_usage(args: argparse.Namespace) -> int:
    from us_mediakit.api.admin.usage import compute_account_usage
    from us_mediakit.db.engine import create_db_engine, create_session_factory

    session_factory = create_session_factory(create_db_engine())
    with session_factory() as session:
        result = compute_account_usage(
            session, args.account_ref, from_=args.date_from, to=args.date_to
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("us_mediakit.server:app", host=args.host, port=args.port)
    return 0


def _cmd_watermark_visible(args: argparse.Namespace) -> int:
    from us_mediakit.watermark.visible import VisibleWatermarkError, apply_logo, apply_text

    data = Path(args.source).read_bytes()
    try:
        if args.logo:
            result = apply_logo(
                data, Path(args.logo).read_bytes(), position=args.position, opacity=args.opacity
            )
        elif args.text:
            result = apply_text(data, args.text, position=args.position, opacity=args.opacity)
        else:
            print("Entweder --logo oder --text angeben.", file=sys.stderr)
            return 1
    except VisibleWatermarkError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    Path(args.source).write_bytes(result)
    print(f"Geschrieben: {args.source}")
    return 0


def _cmd_watermark_invisible(args: argparse.Namespace) -> int:
    import secrets

    from us_mediakit.watermark.invisible import REFERENCE_ID_LENGTH_BYTES, WatermarkError, embed

    data = Path(args.source).read_bytes()
    reference_id = bytes.fromhex(args.reference_id) if args.reference_id else secrets.token_bytes(
        REFERENCE_ID_LENGTH_BYTES
    )

    try:
        result = embed(data, reference_id, output_format=args.format)
    except WatermarkError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    Path(args.source).write_bytes(result)
    print(f"Geschrieben: {args.source}")
    print(f"reference_id: {reference_id.hex()}")
    return 0


def _cmd_watermark_detect(args: argparse.Namespace) -> int:
    from us_mediakit.watermark.detect import detect

    data = Path(args.source).read_bytes()
    result = detect(data)

    if args.json:
        print(
            json.dumps(
                {
                    "detected": result.detected,
                    "reference_id": result.reference_id.hex() if result.reference_id else None,
                }
            )
        )
    elif result.detected and result.reference_id is not None:
        print(f"erkannt: reference_id={result.reference_id.hex()}")
    else:
        print("nicht erkannt")
    return 0 if result.detected else 1


def _cmd_animated_webp(args: argparse.Namespace) -> int:
    from us_mediakit.media.animated_webp import AnimatedWebpError, extract_animated_webp

    data = Path(args.source).read_bytes()
    try:
        result = extract_animated_webp(
            data,
            start_seconds=args.start,
            duration_seconds=args.duration,
            width=args.width,
            fps=args.fps,
            quality=args.quality,
        )
    except AnimatedWebpError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_bytes(result)
        print(f"Geschrieben: {args.output}")
    else:
        sys.stdout.buffer.write(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="us-mediakit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    thumbnail = subparsers.add_parser("thumbnail", help="Zuschnitt/Resize gemäß Preset")
    thumbnail.add_argument("source")
    thumbnail.add_argument("--mode", help="Preset-Name aus imageformats.json (optional -- Alternative: --width/--height)")
    thumbnail.add_argument("--width", type=int, help="Zielbreite, als Alternative zu --mode (mit --height zusammen angeben)")
    thumbnail.add_argument("--height", type=int, help="Zielhöhe, als Alternative zu --mode (mit --width zusammen angeben)")
    thumbnail.add_argument(
        "--fit", default="full", choices=["crop", "greedycrop", "greedyscalecrop", "full"],
        help="Fit-Modus, nur relevant zusammen mit --width/--height (Default full).",
    )
    thumbnail.add_argument("--crop", choices=["crop", "greedycrop", "greedyscalecrop"])
    thumbnail.add_argument("--format", default="jpg")
    thumbnail.add_argument("--aspect-ratio", dest="aspect_ratio")
    thumbnail.add_argument(
        "--align-x",
        dest="align_x",
        default=None,
        help="Horizontale Ausrichtung des Ausschnitts bei greedyscalecrop/full: 'left'/'center'/'right' "
        "oder ein Prozentwert 0-100. Ohne Angabe gilt die Ausrichtung aus dem Preset (Default center).",
    )
    thumbnail.add_argument(
        "--align-y",
        dest="align_y",
        default=None,
        help="Vertikale Ausrichtung des Ausschnitts bei greedyscalecrop/full: 'top'/'center'/'bottom' "
        "oder ein Prozentwert 0-100. Ohne Angabe gilt die Ausrichtung aus dem Preset (Default center).",
    )
    thumbnail.add_argument("--zoom")
    thumbnail.add_argument(
        "--max-upscale-factor",
        dest="max_upscale_factor",
        type=float,
        default=None,
        help="Explizites Opt-in für einfache (bikubische) Vergrößerung ohne KI-Provider, "
        "bis zu diesem Faktor (z. B. 2.0 = bis maximal doppelte Größe). Ohne Angabe wird "
        "weiterhin nicht vergrößert, wie bisher.",
    )
    thumbnail.add_argument("--video", action="store_true")
    thumbnail.add_argument(
        "--video-seek-seconds",
        dest="video_seek_seconds",
        type=float,
        default=DEFAULT_SEEK_SECONDS,
        help=f"Zeitpunkt für die Frame-Extraktion bei --video, in Sekunden (Default {DEFAULT_SEEK_SECONDS}). "
        "Wird automatisch auf die Videodauer geklemmt, wenn das Video kürzer ist.",
    )
    thumbnail.add_argument("--pdf", action="store_true")
    thumbnail.add_argument("--pdf-page", type=int, default=1)
    thumbnail.add_argument("--dry-run", action="store_true")
    thumbnail.add_argument(
        "--no-carry-metadata", dest="carry_metadata", action="store_false", default=True
    )
    thumbnail.add_argument("--strip-gps", action="store_true")
    thumbnail.add_argument(
        "--no-carry-c2pa", dest="carry_c2pa", action="store_false", default=True
    )
    thumbnail.add_argument("--c2pa-cert", help="PEM-Zertifikatskette für die Provenienz-Signatur")
    thumbnail.add_argument("--c2pa-key", help="PEM-Privatschlüssel für die Provenienz-Signatur")
    thumbnail.add_argument(
        "--c2pa-json",
        help="JSON-Datei mit optionalem digital_source_type/actions/assertions-Override",
    )
    thumbnail.add_argument("-o", "--output")
    thumbnail.set_defaults(func=_cmd_thumbnail)

    c2pa_parser = subparsers.add_parser("c2pa", help="Content Credentials prüfen/signieren")
    c2pa_sub = c2pa_parser.add_subparsers(dest="c2pa_command", required=True)

    c2pa_verify_parser = c2pa_sub.add_parser("verify")
    c2pa_verify_parser.add_argument("source")
    c2pa_verify_parser.add_argument("--mime-type")
    c2pa_verify_parser.set_defaults(func=_cmd_c2pa_verify)

    c2pa_sign_parser = c2pa_sub.add_parser("sign")
    c2pa_sign_parser.add_argument("source")
    c2pa_sign_parser.add_argument("--cert", required=True)
    c2pa_sign_parser.add_argument("--key", required=True)
    c2pa_sign_parser.add_argument("--source-type", required=True, dest="source_type")
    c2pa_sign_parser.add_argument("--actions-json")
    c2pa_sign_parser.add_argument("--mime-type")
    c2pa_sign_parser.set_defaults(func=_cmd_c2pa_sign)

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

    admin = subparsers.add_parser("admin", help="API-Keys/Nutzung verwalten")
    admin_sub = admin.add_subparsers(dest="admin_command", required=True)

    admin_api_key = admin_sub.add_parser("api-key")
    admin_api_key_sub = admin_api_key.add_subparsers(dest="api_key_command", required=True)

    admin_api_key_create = admin_api_key_sub.add_parser("create")
    admin_api_key_create.add_argument("--account-ref", required=True, dest="account_ref")
    admin_api_key_create.add_argument("--label", required=True)
    admin_api_key_create.set_defaults(func=_cmd_admin_api_key_create)

    admin_api_key_suspend = admin_api_key_sub.add_parser("suspend")
    admin_api_key_suspend.add_argument("key_id")
    admin_api_key_suspend.set_defaults(func=_cmd_admin_api_key_suspend)

    admin_usage = admin_sub.add_parser("usage")
    admin_usage.add_argument("account_ref")
    admin_usage.add_argument("--from", dest="date_from", type=datetime.fromisoformat)
    admin_usage.add_argument("--to", dest="date_to", type=datetime.fromisoformat)
    admin_usage.set_defaults(func=_cmd_admin_usage)

    serve = subparsers.add_parser("serve", help="Netzwerk-Dienst starten (Entwicklung)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=_cmd_serve)

    watermark_parser = subparsers.add_parser("watermark", help="Wasserzeichen anbringen/erkennen")
    watermark_sub = watermark_parser.add_subparsers(dest="watermark_command", required=True)

    watermark_visible = watermark_sub.add_parser("visible", help="Sichtbares Wasserzeichen (Logo/Text)")
    watermark_visible.add_argument("source")
    watermark_visible.add_argument("--logo", help="Pfad zu einem Logo-Bild")
    watermark_visible.add_argument("--text", help="Alternativ ein Schriftzug")
    watermark_visible.add_argument("--position", default="bottom-right")
    watermark_visible.add_argument("--opacity", type=float, default=0.6)
    watermark_visible.set_defaults(func=_cmd_watermark_visible)

    watermark_invisible = watermark_sub.add_parser("invisible", help="Unsichtbares Wasserzeichen (Embedding)")
    watermark_invisible.add_argument("source")
    watermark_invisible.add_argument(
        "--reference-id", dest="reference_id", help="4 Byte hex; ohne Angabe wird eine erzeugt"
    )
    watermark_invisible.add_argument(
        "--format",
        default="JPEG",
        help="Ausgabeformat, unabhängig von der Dateiendung des Quellpfads (Default JPEG). "
        "Wichtig für Robustheitstests: JPEG kodiert beim Einbetten bereits verlustbehaftet.",
    )
    watermark_invisible.set_defaults(func=_cmd_watermark_invisible)

    watermark_detect = watermark_sub.add_parser("detect", help="Unsichtbares Wasserzeichen erkennen")
    watermark_detect.add_argument("source")
    watermark_detect.add_argument("--json", action="store_true")
    watermark_detect.set_defaults(func=_cmd_watermark_detect)

    animated_webp = subparsers.add_parser(
        "animated-webp", help="Animierten WebP-Ausschnitt aus einem Video erzeugen"
    )
    animated_webp.add_argument("source")
    animated_webp.add_argument("--start", type=float, default=0.0)
    animated_webp.add_argument("--duration", type=float, default=3.0)
    animated_webp.add_argument("--width", type=int, default=None)
    animated_webp.add_argument("--fps", type=int, default=12)
    animated_webp.add_argument("--quality", type=int, default=75)
    animated_webp.add_argument("-o", "--output")
    animated_webp.set_defaults(func=_cmd_animated_webp)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
