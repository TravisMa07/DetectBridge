"""Compile the frozen independent rule packet; never derive expected outcomes."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(root / "tools"))
from detection_compile import compile_rules
from lifecycle_validation import bundle, encoded

fixtures = root / "contracts/lifecycle-runtime/v1/fixtures"
references = json.loads((fixtures / "source-references.json").read_bytes())["sources"]
provenance = json.loads((fixtures / "provenance.json").read_bytes())["rules"]
sources = [json.loads((root / item["source"]["path"]).read_bytes()) for item in references]
mappings = [json.loads((root / item["mapping"]["path"]).read_bytes()) for item in references]
output = root / "packages/lifecycle-job/build/fixtures"
output.mkdir(parents=True, exist_ok=True)
for phase in ("a", "b"):
    names = [f"rules/{phase}-windows.yml", f"rules/{phase}-linux.yml"]
    plan = compile_rules([fixtures / name for name in names], sources, mappings=mappings, provenance=[provenance[name] for name in names])
    data = encoded(plan)
    (output / f"{phase}.plan.json").write_bytes(data)
    (output / f"{phase}.manifest.json").write_bytes(encoded(bundle(data)))
