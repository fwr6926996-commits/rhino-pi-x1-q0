"""Host-only integrity check. Does not import AidLite or run models."""
import hashlib
import json
from pathlib import Path
import statistics


def main():
    root = Path(__file__).resolve().parent.parent
    checked = 0
    for line in (root / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = root / name
        if not path.resolve().is_relative_to(root):
            raise SystemExit("Unsafe manifest path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit("Hash mismatch: " + name)
        checked += 1
    records = json.loads((root / "evidence/results.json").read_text())
    samples = 0
    for run in records["runs"]:
        if "timing_ms" not in run:
            if run["invokes"] != 0:
                raise SystemExit("Missing timing for completed run")
            continue
        timing = run["timing_ms"]
        values = timing["values"]
        if len(values) != run["invokes"] or len(values) != 10:
            raise SystemExit("Unexpected sample count")
        for key, value in (("mean", statistics.mean(values)), ("min", min(values)), ("max", max(values))):
            if abs(timing[key] - value) > 1e-10:
                raise SystemExit("Inconsistent timing: " + run["id"])
        samples += len(values)
    print(f"PASS: {checked} public files; {samples} recorded timing samples. No device access.")


if __name__ == "__main__":
    main()
