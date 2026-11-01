# Example: a claim proven end to end

A deliberately tiny synthetic target, in two builds: **vulnerable** (pays a caller-chosen recipient
without asking it to approve) and **fixed** (requires the recipient's signature).

Run the verifier from the repository root:

```bash
python3 verifikator/verifikator.py examples/vault/spec.json
```

Expected result:

```
run: examples/vault/vulnerable :: attack_withdraw_without_signature (must pass)
  passed=True · MET
run: examples/vault/fixed :: attack_withdraw_without_signature (must fail)
  passed=False · MET
verdict: CONFIRMED
```

Remove the signature check from `fixed/src/lib.rs` and the verdict turns `REFUTED` — which is the
point: the second build is what makes the first result mean anything.

Nothing above runs against a network or a deployed program; it executes on a local runtime.
