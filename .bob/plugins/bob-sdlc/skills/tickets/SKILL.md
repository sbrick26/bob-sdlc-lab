---
name: tickets
description: "Check my tickets": list the Jira tickets assigned to the signed-in user, recommend one, and start it on a yes. Use when the user asks what to work on, says "check my tickets", or runs /tickets.
metadata:
  user-invocable: true
---

# Check my tickets

You act as the signed-in user through the Jira MCP server. Jira knows who that is.

Jira actions and the tool names you may see (use whichever server is connected):

| Action | Atlassian hosted server (OAuth) | atlassian-token server |
|---|---|---|
| find my site id | getAccessibleAtlassianResources (first id = cloudId) | not needed |
| search | searchJiraIssuesUsingJql | jira_search |
| read one | getJiraIssue | jira_get_issue |
| change status | transitionJiraIssue (if hidden: discover, then executeWrite) | jira_get_transitions then jira_transition_issue |
| comment | addOrEditJiraIssueComment (same discover path) | jira_add_comment |

Steps:
1. Search with JQL: `assignee = currentUser() AND status != Done ORDER BY status DESC, priority ASC, created ASC`, fields summary, status, priority, description.
2. Show a short table: key, title, status, priority. One line per ticket. No descriptions yet.
3. Recommend one: In Progress first, else the highest priority To Do. One sentence why.
4. Ask "Start <KEY>?" and stop. Do not start without a yes.
5. On yes: move the ticket to In Progress, add the comment "Started with Bob", then say: "Run /plan <KEY> to write the spec."

Never pick a ticket assigned to someone else. If the search returns nothing, say so and suggest asking the lead.
