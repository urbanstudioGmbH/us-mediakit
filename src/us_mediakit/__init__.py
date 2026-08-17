__version__ = "0.1.0.dev0"

# HEIC/HEIF ist kein von Pillow selbst mitgeliefertes Format — pillow-heif muss seinen
# Opener/Encoder einmal registrieren, bevor Image.open()/save() diese Formate kennen.
# An einer zentralen Stelle (Paket-Import), damit es unabhängig davon passiert, welches
# Modul als erstes ein Bild dekodiert/kodiert. AVIF braucht das nicht — das ist in
# aktuellen Pillow-Wheels nativ enthalten (siehe core/formats.py::is_write_format_available).
import pillow_heif

pillow_heif.register_heif_opener()
