---
name: spec
description: Turn one Jira ticket into plans/<KEY>.md in the required plan format, post the summary to Jira, move the ticket to In Review, and ask the requester to approve. Use in the Plan mode or when the user runs /plan <KEY>.
---

# Spec

1. Read the ticket with getJiraIssue. Read tickets/ in the repo if a matching file exists; it may carry hints.
2. Read only the files the ticket names and their direct imports. Do not survey the whole repo.
3. Write plans/<KEY>.md using the plan format in your mode rules. Acceptance criteria come from the ticket's "Done when" list, rewritten so each is checkable.
4. Work units must stay inside the files the ticket allows. If the ticket's "touches" list conflicts with what you need, write it under Open questions with your default.
5. Post one Jira comment: the "What I understood" paragraph, the acceptance criteria, and the path plans/<KEY>.md. Keep it under 15 lines.
6. Move the ticket to In Review.
7. If CONFLUENCE_SPACE is set in the environment, also create a Confluence page titled "<KEY> spec" under the parent page named "FieldOps specs" with the same content, using createConfluenceContent.
8. Stop with: "Spec posted. Requester: reply approve, or tell me what to change."

When the requester approves: set "Requester approval: approved by <name>" in the plan, and say "Run /build <KEY>."
