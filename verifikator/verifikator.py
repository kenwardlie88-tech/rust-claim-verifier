#!/usr/bin/env python3
"""Fail-closed verification harness for audit claims (Rust / Solana).

Invariants that cannot be bypassed:
  1. Every expectation must carry an OBSERVED value (real `cargo test` output).
  2. At least one expectation must be "pass" (attack succeeds on the vulnerable build)
     AND one must be "fail" (attack is rejected on the fixed build). Without both
     sides the verdict is refused: a pass without a negative control is not evidence.
  3. The `not_claimed` list must be present and non-empty.
  4. A verdict is CONFIRMED only when every expectation is met; otherwise REFUTED.

Usage:
    python3 verifikator.py spec.json
Exit codes: 0 = CONFIRMED · 1 = REFUTED · 2 = REFUSED (incomplete spec / unmeasurable)
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE / "evidence" / "verdicts"


def run_test(project: str, test_name: str) -> dict:
    """Run one test in one project and return the observed result."""
    target = BASE / project
    if not (target / "Cargo.toml").exists():
        return {"ok": None, "reason": f"project not found: {target}"}

    # Portable: load a local env.sh only if the caller ships one (optional).
    env_file = BASE / "env.sh"
    prefix = f"source {env_file} >/dev/null 2>&1; " if env_file.exists() else ""
    command = (
        f"{prefix}cd {target} && "
        f"cargo test --release --test poc -- --exact {test_name} --nocapture"
    )
    result = subprocess.run(
        ["bash", "-lc", command], capture_output=True, text=True, timeout=1800
    )
    output = result.stdout + result.stderr

    passed_re = re.compile(rf"test {re.escape(test_name)} \.\.\. ok")
    failed_re = re.compile(rf"test {re.escape(test_name)} \.\.\. FAILED")
    if passed_re.search(output):
        passed = True
    elif failed_re.search(output) or result.returncode != 0:
        passed = False
    else:
        return {"ok": None, "reason": "test produced no readable status"}

    return {
        "ok": passed,
        "project": project,
        "test": test_name,
        "exit": result.returncode,
        "evidence_lines": [
            line.strip()
            for line in output.splitlines()
            if test_name in line and ("ok" in line or "FAILED" in line or "panicked" in line)
        ][:3],
    }


def refuse(reason: str) -> int:
    print(f"  REFUSED: {reason}")
    return 2


def main() -> int:
    if len(sys.argv) < 2:
        return refuse("provide a specification file (JSON)")

    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    finding_id = spec.get("id", "").strip()
    claim = spec.get("claim", "").strip()
    expectations = spec.get("expectations", [])
    not_claimed = [n for n in spec.get("not_claimed", []) if n.strip()]

    if not finding_id:
        return refuse("missing 'id'")
    if not claim:
        return refuse("missing 'claim' — nothing to verify")
    if not not_claimed:
        return refuse("'not_claimed' is empty — the limits of the proof must be stated")
    if not expectations:
        return refuse("no expectations to test")

    must_pass = [e for e in expectations if e.get("must") == "pass"]
    must_fail = [e for e in expectations if e.get("must") == "fail"]
    if not must_pass or not must_fail:
        return refuse(
            "two-sided control missing: need at least one 'pass' (vulnerable build) and "
            "one 'fail' (fixed build). A pass without a negative control is not evidence."
        )

    observed = []
    for expectation in expectations:
        print(f"  run: {expectation['project']} :: {expectation['test']} (must {expectation['must']})")
        result = run_test(expectation["project"], expectation["test"])
        if result.get("ok") is None:
            return refuse(f"unmeasurable — {result.get('reason')}")
        result["must"] = expectation["must"]
        result["met"] = (result["ok"] is True and expectation["must"] == "pass") or (
            result["ok"] is False and expectation["must"] == "fail"
        )
        observed.append(result)
        print(f"    passed={result['ok']} · {'MET' if result['met'] else 'NOT MET'}")

    verdict = "CONFIRMED" if all(o["met"] for o in observed) else "REFUTED"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "id": finding_id,
        "claim": claim,
        "verdict": verdict,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "expectations": observed,
        "not_claimed": not_claimed,
        "environment": {
            "script": str(Path(__file__).resolve()),
            "base": str(BASE),
            "python": sys.version.split()[0],
        },
    }
    (OUTPUT_DIR / f"{finding_id}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        f"# Verification verdict {finding_id}",
        "",
        f"**Claim:** {claim}",
        f"**Verdict:** **{verdict}**",
        f"**Timestamp:** {record['timestamp']}",
        "",
        "## Expectations vs observed",
        "",
        "| Project | Test | Must | Observed | Met |",
        "|---|---|---|---|---|",
    ]
    for o in observed:
        lines.append(
            f"| {o['project']} | `{o['test']}` | {o['must']} | "
            f"{'pass' if o['ok'] else 'fail'} | {'yes' if o['met'] else 'NO'} |"
        )
    lines += ["", "## Not claimed", ""] + [f"- {n}" for n in not_claimed]
    (OUTPUT_DIR / f"{finding_id}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"  verdict: {verdict}")
    print(f"  saved: {OUTPUT_DIR / (finding_id + '.json')}")
    return 0 if verdict == "CONFIRMED" else 1


if __name__ == "__main__":
    sys.exit(main())
