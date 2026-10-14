# Plan format (plans/<KEY>.md)

Use exactly these headings, in this order. Short sentences. A requester must be able to read it in two minutes.

1. Ticket: key, title, requester, link.
2. What I understood: one paragraph in plain words.
3. Design decisions: each question you asked, the answer, and what it changes. Write "default" when the user accepted your default.
4. Open questions: anything still undecided, each with a proposed default. Say "none" if none.
5. Acceptance criteria: 3 to 6 bullets, each one checkable by a non-developer.
6. Test plan: which tests prove each criterion. Name the test file.
7. Work units: the files to create or change, one line each. Nothing else may change.
8. Out of scope: what this ticket does not do.
9. Risk and compliance: personal data, secrets, data loss, rollback. One line each or "none".
10. Approval: "Requester approval: pending" until the requester approves.
