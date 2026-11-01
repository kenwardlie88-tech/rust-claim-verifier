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
   vulnerable build) and at least one to *fail* (attack is rejected on the fixed build).
   A test that passes on both builds proves nothing — so the tool refuses.
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
  "klaim": "pemanggil tanpa hak dapat memindahkan dana keluar dari vault yang bukan miliknya",
  "harapan": [
    { "proyek": "programs/target-rentan",     "tes": "serangan_memindahkan_dana", "harus": "lulus" },
    { "proyek": "programs/target-diperbaiki", "tes": "serangan_memindahkan_dana", "harus": "gagal" }
  ],
  "tidak_diklaim": [
    "tidak membuktikan isu ini ada pada program yang sudah ter-deploy",
    "tidak menguji jalur reentrancy"
  ]
}
```

Key names are Indonesian (`klaim` = claim, `harapan` = expectations, `harus` = must,
`tidak_diklaim` = not claimed) because the tool was written and tested that way; rename them in the
source if you prefer another language.

## Why two-sided controls

A test that cannot fail is decoration. The fixed build is what makes the test honest: if the
attack still passes after the fix, then either the fix is incomplete or the test is measuring the
wrong thing. Either way, there is no finding — there is a hypothesis.

## Requirements

- Rust toolchain, `cargo`
- Target projects as Cargo crates containing an integration test binary (`--test poc`)
- No network, no mainnet interaction: everything runs on a local runtime

## License

MIT
