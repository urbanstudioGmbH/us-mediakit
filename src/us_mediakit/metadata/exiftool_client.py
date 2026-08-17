"""Langlebiger exiftool-Subprozess ("-stay_open"-Modus).

`exiftool` selbst startet (Perl-Interpreter-Start) mit einigen zehn Millisekunden pro
Aufruf — bei vielen Anfragen pro Sekunde (Netzwerk-Dienst, Phase 4) summiert sich das.
Der "-stay_open True"-Modus hält einen einzigen exiftool-Prozess dauerhaft am Leben:
Kommandos werden zeilenweise über stdin geschickt, durch eine `-executeNNNN`-Zeile
abgeschlossen, die Antwort endet mit der dazu passenden `{readyNNNN}`-Markierung auf
stdout. Diese numerierten Marker (statt des schlichten `-execute`/`{ready}` aus den
einfachsten exiftool-Beispielen) sind exiftools eigene empfohlene Variante, um Antworten
eindeutig ihrem Kommando zuordnen zu können.

Ein Client-Objekt entspricht **einem** Worker/Thread — der exiftool-Prozess verarbeitet
Kommandos ausschließlich seriell, ein `threading.Lock` verhindert das Verschränken
paralleler Aufrufe innerhalb desselben Clients (siehe Programmierplan Abschnitt 7,
"ein langlebiger Prozess pro Worker").
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any


class ExifToolError(RuntimeError):
    pass


class ExifToolClient:
    def __init__(self, executable: str = "exiftool") -> None:
        self._executable = executable
        self._lock = threading.Lock()
        self._counter = 0
        self._process: subprocess.Popen[bytes] | None = None
        self._start()

    def _start(self) -> None:
        self._process = subprocess.Popen(
            [self._executable, "-stay_open", "True", "-@", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _execute(self, args: list[str]) -> bytes:
        if self._process is None or self._process.poll() is not None:
            self._start()
        assert self._process is not None
        assert self._process.stdin is not None
        assert self._process.stdout is not None

        with self._lock:
            self._counter += 1
            marker = f"{self._counter:04d}"
            ready_marker = f"{{ready{marker}}}"

            command = "\n".join([*args, f"-execute{marker}", ""]).encode("utf-8")
            self._process.stdin.write(command)
            self._process.stdin.flush()

            output = bytearray()
            ready_bytes = ready_marker.encode("utf-8")
            while ready_bytes not in output:
                chunk = self._process.stdout.read(1)
                if not chunk:
                    raise ExifToolError("exiftool-Prozess wurde unerwartet beendet.")
                output.extend(chunk)

            return bytes(output[: -len(ready_bytes)]).rstrip(b"\r\n")

    def run_raw(self, args: list[str]) -> bytes:
        """Führt beliebige exiftool-Argumente aus, roh, ohne Interpretation der Antwort."""
        return self._execute(args)

    def read_tags(self, path: str | Path, *, groups: bool = True) -> dict[str, Any]:
        args = ["-j"]
        if groups:
            args.append("-G")
        args.append(str(path))
        raw = self._execute(args)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExifToolError(f"exiftool-Ausgabe konnte nicht als JSON gelesen werden: {raw!r}") from exc
        if not parsed:
            raise ExifToolError(f"exiftool hat keine Metadaten für {path!r} zurückgegeben.")
        return parsed[0]

    def write_tags(self, path: str | Path, tags: dict[str, str]) -> None:
        args = [f"-{key}={value}" for key, value in tags.items()]
        args.append("-overwrite_original")
        args.append(str(path))
        raw = self._execute(args)
        if b"error" in raw.lower():
            raise ExifToolError(f"exiftool-Schreibfehler: {raw!r}")

    def close(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        assert self._process.stdin is not None
        try:
            self._process.stdin.write(b"-stay_open\nFalse\n-execute\n")
            self._process.stdin.flush()
            self._process.wait(timeout=5)
        except (BrokenPipeError, subprocess.TimeoutExpired):
            self._process.kill()

    def __enter__(self) -> ExifToolClient:  # noqa: PYI034 — typing.Self braucht Py 3.11+, wir unterstützen 3.10
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
