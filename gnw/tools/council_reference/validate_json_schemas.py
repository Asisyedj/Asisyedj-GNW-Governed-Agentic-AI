from pathlib import Path
import json

root = Path(__file__).parents[2] / "src" / "server" / "council" / "schemas"
files = sorted(root.glob("*.json"))
assert len(files) == 6, files
for path in files:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert value["$schema"].startswith("https://json-schema.org/")
    assert value["additionalProperties"] is False
print(f"validated_json_schemas={len(files)}")
