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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
