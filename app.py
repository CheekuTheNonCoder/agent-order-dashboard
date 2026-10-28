"""OrderOS agent dashboard — loader.

The full application body is stored in _app_part_*.txt shards so large
updates can be pushed reliably. This file concatenates them and executes
the combined source (same behavior as a single app.py).
"""
from pathlib import Path

_parts = sorted(Path(__file__).parent.glob("_app_part_*.txt"))
if not _parts:
    raise RuntimeError(
        "Missing _app_part_*.txt shards next to app.py. "
        "Redeploy with the full OrderOS app package."
    )
_src = "".join(p.read_text(encoding="utf-8") for p in _parts)
exec(compile(_src, str(Path(__file__).resolve()), "exec"), globals())
