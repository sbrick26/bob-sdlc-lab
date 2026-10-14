---
name: new-check
description: >-
  Add a new item to the PR checklist that the pr-gate hook enforces on every push. Use when someone says "every PR must also ...". Stretch exercise for the lab.
metadata:
  user-invocable: true
---

# New check

The checklist lives in .bob/governance/pr-checklist.yaml. Each item has: id, says (plain words), type, value.
Types: branch_not, file_exists (value may contain {KEY}), file_contains (path, value), marker (a file name in the hooks' scratch folder <git dir>/bob-run/), command_not_contains (list). Paths are from the repo root, for example fieldops-repo/plans/{KEY}.md.

1. Ask what the rule is in one sentence. Pick the type. If none fits, say so; adding a type is a code change in .bob/hooks/pr_gate.py.
2. This path is protected. Make the change on a branch named <name>/governance-<short>, open a PR to the platform owner.
3. Show the user the new item and explain in one line when it will block.
