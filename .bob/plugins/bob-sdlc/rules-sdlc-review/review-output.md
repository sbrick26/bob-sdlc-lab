# Review output

End every review with this block and nothing after it:

VERDICT: PASS | FAIL
CRITERIA: <met>/<total>
FINDINGS:
- [blocking|advisory] <file>:<line> <one sentence>
RULES: <ok | list of rule files violated>
TESTS: <passed>/<total> | not run

PASS only if every acceptance criterion is met, tests pass, and no blocking finding exists.
