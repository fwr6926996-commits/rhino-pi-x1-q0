"""Q0-SAMPLE-03 CPU control target supervisor. Owner continuation recorded separately.

Send to X1 through ADB stdin only after Owner approval of the matching plan.
The vendor sample is copied without edits and launched at most once per run_id.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

EXPECTED = {'/usr/local/share/aidlite/examples/aidlite_tflite/python/tflite_yolov5_multi.py': '88ae8564a835f4bd1a6fb01f44c238a48236d8e12391863fc04c0f0f8fb3b126', '/usr/local/share/aidlite/examples/aidlite_tflite/data/tflite_yolov5_multi/cutoff_yolov5s_640_int8.tflite': '3f1eb9278f59f059e1ac84195f40ea98f292f2463c032b58e3100fa6a6b00dfb', '/usr/local/share/aidlite/examples/aidlite_tflite/data/tflite_yolov5_multi/bus.jpg': 'fb4914d123d97c440cd127ef0e98d4bdc68cd88e2683657528928b4a34014e16', '/usr/local/lib/libaidlite.so': '4807e38faec82f9e3065be1009233c68ae09f5a98aa0dd3a6cbc42f9e1a19dab', '/usr/local/lib/libaidlite_tflite.so': 'fdc1424cc33a09aa5a4412e1af09564a41a2b940b1e3ce19a11fcd87845a307e', '/usr/local/lib/aidlux/aidlite/tflite/delegate/libQnnTFLiteDelegate.so': 'c59d38cd51c40286729ff0a44a55f00cdcff5c205ee94472df6852ba6b7e3d49', '/usr/local/lib/aidlux/aidlite/tflite/delegate/libQnnHtp.so': '43bf07ab906918f046277da76703a01d56932bb078250cd1dd805c77d7390e78', '/usr/local/lib/aidlux/aidlite/tflite/delegate/libQnnSystem.so': 'a65251f0c706f7dc27e15893f5232d7bde2198cdec4502fb49c5f76b626997c7', '/usr/local/lib/aidlux/aidlite/tflite/delegate/libQnnHtpPrepare.so': 'bfa90f1fe3b2aff80d53c52ead2a0dffdba6d2be0db6b9f0cf1a50195fe221e0', '/usr/local/lib/aidlux/aidlite/tflite/delegate/libQnnHtpV73Stub.so': '25927932e927dff847f38296ea9c801c4d80c42aa55660dde77e53c3e2dfba0a', '/usr/local/lib/aidlux/aidlite/tflite/delegate/libQnnHtpV73Skel.so': '13249311402f735b81396a85af4699b35fae3676e722a2848ace25c0510c20f6'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-approved", action="store_true")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.owner_approved:
        parser.error("explicit Owner authorization is required before execution")
    if not re.fullmatch(r"Q0-SAMPLE-03-[0-9]{8}-[0-9]{2}", args.run_id):
        parser.error("invalid run_id")
    if os.geteuid() != 2000:
        raise SystemExit("STOPPED_UID_CHANGED: expected existing ADB uid 2000")
    actual = {p: digest(p) for p in EXPECTED}
    if actual != EXPECTED:
        print(json.dumps({"status": "STOPPED_HASH_DRIFT", "actual": actual}))
        return 3

    # Exclusive directory creation prevents reusing this run_id, even after failure.
    work = Path("/tmp") / ("rhino-x1-" + args.run_id)
    work.mkdir()
    (work / "python").mkdir()
    (work / "tmp").mkdir()
    base = Path("/usr/local/share/aidlite/examples/aidlite_tflite")
    (work / "data").symlink_to(base / "data", target_is_directory=True)
    copied = work / "python/tflite_yolov5_multi.py"
    copied.write_bytes((base / "python/tflite_yolov5_multi.py").read_bytes())
    if digest(copied) != EXPECTED[str(base / "python/tflite_yolov5_multi.py")]:
        raise SystemExit("STOPPED_COPY_HASH_MISMATCH")
    cmd = ["python3", "-B", "./tflite_yolov5_multi.py", "1"]
    result = {
        "experiment": "Q0-SAMPLE-03",
        "run_id": args.run_id,
        "scope": "single existing TFLite CPU control sample; no automatic retry",
        "owner_approval_flag_is_not_authorization_evidence": True,
        "status": "STARTING",
        "uid": os.geteuid(),
        "target_workdir": str(work),
        "command": cmd,
        "cwd": str(work / "python"),
        "requested_backend": "TYPE_CPU",
        "framework": "TYPE_TFLITE",
        "maximum_launches": 1,
        "configured_invoke_count": 10,
        "timeout_seconds": 120,
        "source_hashes_before": actual,
        "started_at_target_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "os_release": Path("/etc/os-release").read_text(),
        "kernel": Path("/proc/version").read_text().strip(),
    }
    with (work / "attempt.json").open("x") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({"event": "PRECHECK_OK", "target_workdir": str(work)}), flush=True)
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", TMPDIR=str(work / "tmp"))
    timed_out = False
    start = time.monotonic_ns()
    with (work / "stdout.txt").open("wb") as sout, (work / "stderr.txt").open("wb") as serr:
        proc = subprocess.Popen(cmd, cwd=work / "python", env=env,
                                stdout=sout, stderr=serr, start_new_session=True)
        result["sample_pid"] = proc.pid
        try:
            rc = proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                rc = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                rc = proc.wait(timeout=5)
    result.update(
        status="STOPPED_TIMEOUT" if timed_out else "PROCESS_FINISHED_REVIEW_REQUIRED",
        exit_code=rc,
        timed_out=timed_out,
        target_supervisor_elapsed_ns=time.monotonic_ns() - start,
        finished_at_target_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
    after = {p: digest(p) for p in EXPECTED}
    result["source_hashes_after"] = after
    result["source_assets_unchanged"] = after == EXPECTED
    result["artifacts"] = {}
    # Restrict collection to known run outputs; never recurse through the data link.
    for name in ("attempt.json", "stdout.txt", "stderr.txt",
                 "python/tflite_yolov5_multi.py", "python/tflite_yolov5_multi.jpg"):
        p = work / name
        if p.is_file():
            result["artifacts"][name] = {"bytes": p.stat().st_size, "sha256": digest(p)}
    (work / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    # Process exit success never substitutes for delegate/HTP and output review.
    return 0 if not timed_out and rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
