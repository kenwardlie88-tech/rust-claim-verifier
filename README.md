# rust-claim-verifier

A small, fail-closed harness for one job: **prove an audit claim, or refuse to record it.**

Most security write-ups are unfalsifiable. You cannot re-run them, and you cannot tell a real
finding from a lucky guess. This tool encodes the opposite discipline.

## The contract

Given a claim and a pair of builds — one **vulnerable**, one **fixed** — the verifier runs the
same test against both and records a verdict only if:

1. **Every expectation has an observed value.** An expectation without an observation is a plan,
   not evidence.
2. **Both sides are present.** At least one test must be expected to *pass* (attack succeeds on the
   vulnerable build) and at least one to *fail* (attack is rejected on the fixed build). A test
   that passes on both builds proves nothing — so the tool refuses.
3. **Non-claims are declared.** The verdict must state what the run does **not** prove.

Violate any of these and the tool exits `2` and writes **nothing**.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | `CONFIRMED` — every expectation met |
| `1` | `REFUTED` — ran, but at least one expectation was not met |
| `2` | `REFUSED` — incomplete specification or unmeasurable result; **no file written** |

## Usage

```bash
python3 verifikator/verifikator.py spec.json
```

Example specification: [`examples/spec.example.json`](examples/spec.example.json).

```json
{
  "id": "V-101",
  "claim": "an unprivileged caller can move funds out of a vault it does not own",
  "expectations": [
    { "project": "programs/target-vulnerable", "test": "attack_moves_funds", "must": "pass" },
    { "project": "programs/target-fixed",      "test": "attack_moves_funds", "must": "fail" }
  ],
  "not_claimed": [
    "does not prove the issue exists in the deployed program",
    "does not cover re-entrancy paths"
  ]
}
```

## Runnable example

[`examples/vault`](examples/vault) is a synthetic two-build target: the attack passes on the
`vulnerable` build and fails on the `fixed` build. Remove the signature check from the fixed build
and the verdict flips to `REFUTED` — which is the point.

```bash
python3 verifikator/verifikator.py examples/vault/spec.json
```

## Why two-sided controls

## Why two-sided controls

A test that cannot fail is decoration. The fixed build is what makes the test honest: if the attack
still passes after the fix, then either the fix is incomplete or the test is measuring the wrong
thing. Either way, there is no finding — there is a hypothesis.

## Requirements

- Rust toolchain and `cargo`
- Each target as a Cargo crate with an integration test binary (`--test poc`)
- No network access and no mainnet interaction: everything runs on a local runtime

## Output

One JSON record plus a Markdown summary per verdict, written to `evidence/verdicts/`, carrying the
observed values, the expected values, and the non-claims list. A verdict without those three parts
is refused before it reaches disk.

## License

MIT
