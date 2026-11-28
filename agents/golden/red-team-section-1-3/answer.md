# Red team: the claims of section 1.3

Public data. Not a client. Not a result.

Nothing in section 1.3 is a result on a real brand, and the section says so itself. Two claims
cannot be shown to anyone outside the project as they stand.

## Verdict table

| Claim | Status | Problem | Fix or test |
|---|---|---|---|
| The naive mean undercounts demand by the expected unmet demand per day | sourced | The proof and its check script are in Hagen's project, not in this repo, so it cannot be re-run here | Move the check script into the repo with its test, then mark it proven |
| Pooling cut slow-seller error by 27% [sourced: SUPPLY_VARIABILITY.md section 1.3], baseline: each store's own demand estimate | inference | A simulation on made-up data, with no held-out test on a real brand | Run it on the first brand's exports against that store's own estimate |
| Pooling 20 businesses won in 51 of 96 cells and in 80 of 96 cells [count] [sourced: SUPPLY_VARIABILITY.md section 1.3] | inference | Simulated. An earlier summary quoted a different count, which the file does not support | Quote the file only, and label it a simulation |
| Lead-time forecast error fell from 5.7 days to 4.0 days with 20 brands pooled [count] [sourced: SUPPLY_VARIABILITY.md section 1.3] | unsupported | The ledger says an earlier simulator had a bug, and the simulator is not in this repo | Re-run the simulator with the bug ruled out, or stop quoting it (O2) |
| The public-data test landed 86.3% of actual profit inside the 90% range [sourced: SUPPLY_VARIABILITY.md section 1.3] | sourced | Grocery data, not e-commerce, and cost was assumed. It shows honest predictions, not that a move causes profit | Shadow mode on the first brand until 8 sealed moves are graded (O18) [count] |
| The fee never billed below a previous peak in 3,000 random histories [count] [sourced: SUPPLY_VARIABILITY.md section 1.3] | sourced | Random histories test the fee's arithmetic, not a brand's behaviour | Re-run on the first brand's graded record |
| No dollar result on a real brand has been proven | proven | None. No brand has installed | Keep saying it, every time |

Verdict: fix first

## Next action

- Take the 5.7 days to 4.0 days figure out of anything a client can read, and keep it out until the simulator is re-run [sourced: SUPPLY_VARIABILITY.md, O2].
