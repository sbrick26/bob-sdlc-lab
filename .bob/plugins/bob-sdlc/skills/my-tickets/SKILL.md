---
name: my-tickets
description: "Check my tickets": list the Jira tickets assigned to the signed-in user, pick the one to start, move it to In Progress. Use when the user asks what to work on, says "check my tickets", or runs /tickets.
---

# Check my tickets

You act as the signed-in user through the atlassian MCP server. Jira knows who that is.

1. If a tool needs a cloudId, call getAccessibleAtlassianResources once and use the first id.
2. Search with JQL: `assignee = currentUser() AND status != Done ORDER BY status DESC, priority ASC, created ASC`.
   Use searchJiraIssuesUsingJql with fields summary, status, priority, description.
3. Show a short table: key, title, status, priority. One line per ticket. No descriptions yet.
4. Recommend one ticket: In Progress first, else the highest priority To Do. Say why in one sentence.
5. Ask: "Start <KEY>?" and stop. Do not start without a yes.
6. On yes: move the ticket to In Progress (transitionJiraIssue; if it is not listed, use discover then executeWrite), add the comment
   "Started by <display name> with Bob", then say: "Run /plan <KEY> to write the spec."

Never pick a ticket assigned to someone else. If the search returns nothing, say so and suggest asking the lead.
