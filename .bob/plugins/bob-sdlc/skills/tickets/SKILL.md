---
name: tickets
description: "Check my tickets": find the user's Jira ticket, work out its stage from Jira and GitHub, and continue with the right skill (plan, build or fix) in the same turn. Use when the user says "check my tickets", asks what to work on, or starts a new chat.
metadata:
  user-invocable: true
---

# Check my tickets

1. Read my-lab.txt at the repo root. It has user, name, team, ticket and the links. Never open lab.env.
2. Find the user's open tickets in Jira, acting as the signed-in user:
   - Hosted Atlassian server: getAccessibleAtlassianResources once for the cloudId, then searchJiraIssuesUsingJql.
   - Token server: jira_search.
   - JQL: `assignee = currentUser() AND status != Done ORDER BY priority ASC, created ASC`. If the environment variable LAB_JQL_OVERRIDE is set, use that JQL instead.
3. If there is more than one, show a short table (key, title, status) and pick the one in my-lab.txt, or ask.
4. Work out the stage with the stage guide in your mode rules (Jira status, the ticket's comments, the pull request and its checks). Say the stage in one line, for example "KAN-158 is approved by the requester and has no pull request yet, so I am starting the build."
5. Continue in the same turn:
   - Stage 1: ask "Start <KEY>?" and stop. On yes, move it to In Progress, comment "Started with Bob", switch to the sdlc-plan mode, load the plan skill and ask the design questions (do not write the spec yet).
   - Stage 2: switch to the sdlc-plan mode and run the plan skill.
   - Stage 4: switch to the sdlc-build mode and run the build skill.
   - Stage 5: switch to the sdlc-build mode and run the fix skill.
   - Stages 3, 6, 7: say what is happening and who acts next. Stop.
6. End every reply with:

   **Your links**
   - Ticket: <jira_ticket from my-lab.txt>
   - Jira board: <jira_board>
   - Your pull requests: <prs>
   - Your activity on the dashboard: <dashboard>

Never pick a ticket assigned to someone else.
