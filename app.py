"""OrderOS agent dashboard — compressed loader."""
import base64, gzip
from pathlib import Path

_parts = sorted(Path(__file__).parent.glob("_app_b64_*.txt"))
if not _parts:
    raise RuntimeError("Missing _app_b64_*.txt next to app.py")
_b64 = "".join(p.read_text(encoding="utf-8").strip() for p in _parts)
_src = gzip.decompress(base64.b64decode(_b64)).decode("utf-8")
exec(compile(_src, str(Path(__file__).resolve()), "exec"), globals())
