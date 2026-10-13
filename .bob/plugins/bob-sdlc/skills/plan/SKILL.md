---
name: plan
description: Write the spec for a ticket. Turns one Jira ticket into plans/<KEY>.md in the required plan format, posts the summary to Jira, moves the ticket to In Review, asks the requester to approve. Use in Plan mode or when the user runs /plan <KEY>.
metadata:
  user-invocable: true
  argument-hint: <TICKET-KEY>
---

Ticket: $1. If you are not in the sdlc-plan mode, switch to it first.
