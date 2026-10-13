---
name: plan
description: Write the spec for a ticket. Turns one Jira ticket into plans/<KEY>.md in the required plan format, posts the summary to Jira, moves the ticket to In Review, asks the requester to approve. Use in Plan mode or when the user runs /plan <KEY>.
metadata:
  user-invocable: true
  argument-hint: <TICKET-KEY>
---

Ticket: $1. If you are not in the sdlc-plan mode, switch to it first.

# Spec

1. Read the ticket (getJiraIssue on the hosted server, jira_get_issue on atlassian-token). Read tickets/ in the repo if a matching file exists; it may carry hints.
2. Read only the files the ticket names and their direct imports. Do not survey the whole repo.
3. Write plans/<KEY>.md using the plan format in your mode rules. Acceptance criteria come from the ticket's "Done when" list, rewritten so each is checkable.
4. Work units must stay inside the files the ticket allows. If the ticket's "touches" list conflicts with what you need, write it under Open questions with your default.
5. Post one Jira comment: the "What I understood" paragraph, the acceptance criteria, and the path plans/<KEY>.md. Keep it under 15 lines.
6. Move the ticket to In Review (transitionJiraIssue, or jira_get_transitions then jira_transition_issue).
7. If CONFLUENCE_SPACE is set in the environment, also create a Confluence page titled "<KEY> spec" under the parent page named "FieldOps specs" with the same content, using the Confluence create tool.
8. Stop with: "Spec posted. Requester: reply approve, or tell me what to change."

When the requester approves: set "Requester approval: approved by <name>" in the plan, and say "Run /build <KEY>."
