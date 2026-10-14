---
name: plan
description: Plan a ticket: ask the user the design questions, write the spec plans/<KEY>.md with the answers and any open questions, review it in chat, and on "I approve" post it to Jira and move the ticket to In Review for the requester. Used by the tickets skill at stage 2, or directly with /plan <KEY> to re-plan.
metadata:
  user-invocable: true
  argument-hint: <TICKET-KEY>
---

Ticket: $1 (or the ticket from my-lab.txt). Work in the sdlc-plan mode; switch to it if you are not in it.

# Plan

1. Read the ticket (getJiraIssue or jira_get_issue) and tickets/ in the repo if a matching file exists. Read only the files it names and their direct imports.
2. Ask 2 to 4 design questions, numbered, each with your proposed default, in one message. Ask only what changes the design: for example the database file location, how to roll back, which fields to mask, what the agent may change. Stop and wait for the answers. "Use the defaults" is a valid answer.
3. Write plans/<KEY>.md in the plan format from your mode rules. Record each question, the answer and what it changes under Design decisions. Put anything still undecided under Open questions with a default.
4. Show the spec in chat: the "What I understood" paragraph, the design decisions, open questions and acceptance criteria. Ask: "Reply **I approve** to send it to the requester, or tell me what to change."
5. If the user asks for changes, update the spec and show it again.
6. On "I approve":
   - post one Jira comment headed "Spec for review" with the understood paragraph, design decisions, open questions and acceptance criteria (under 30 lines);
   - move the ticket to In Review;
   - tell the user: "The spec is on the ticket. The requester approves by commenting Approved there. Then start a new chat and say check my tickets, and I will build it."
7. End with the "Your links" block from the tickets skill.
