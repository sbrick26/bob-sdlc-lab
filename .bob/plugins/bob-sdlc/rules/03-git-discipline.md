# Git discipline

- Work on a branch named <your lab name>/<TICKET-KEY>, for example sam/KAN-157. Never commit on main or demo-dev. Ticket PRs target demo-dev; main is the clean starting point and changes only through platform PRs.
- Commit messages start with the ticket key. Plain messages. No assistant names, no generated-by lines.
- Never use --no-verify, --force, or --force-with-lease. Never rewrite history.
- Push only your own branch. Open the PR with gh. The hook checks the PR checklist before every push.
