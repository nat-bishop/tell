"""Export FastAPI's OpenAPI spec to JSON for frontend codegen."""

import json
from pathlib import Path

from backend.main import app

spec = app.openapi()
out = Path("frontend/src/types/openapi.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(spec, indent=2) + "\n")
print(f"Wrote {out}")
