# Who holds the Jira credential

## 1. What the lab does

| Who | Credential | Where it lives |
|---|---|---|
| Each participant | Own Atlassian sign-in (OAuth) | Bob IDE token store |
| CI | Service-account credential | GitHub Actions secret |

- Server: the official Atlassian MCP server at `https://mcp.atlassian.com/v2/mcp` ([Atlassian docs](https://support.atlassian.com/atlassian-rovo-mcp-server/docs/getting-started-with-the-atlassian-remote-mcp-server/)). Atlassian says OAuth "ensures all actions respect users' existing access controls and permissions".
- Bob IDE: if the server supports OAuth discovery, "you only need to specify the `url`" ([Bob MCP OAuth](https://bob.ibm.com/docs/ide/configuration/mcp/mcp-oauth)). Sign-in opens in the browser. The redirect is `http://127.0.0.1:33418/callback`. To switch accounts, use **Reset auth** in the MCP settings tab.

## 2. When that is not enough

| Need | Why direct OAuth falls short |
|---|---|
| Shared service accounts | CI and bots cannot do a browser sign-in. |
| Central audit | Each call goes from a laptop straight to Atlassian. |
| PII control | Nothing sits between the tool result and the model. |
| Tool allowlists | The user gets every tool the server offers. |
| Token lifetime | The client stores and refreshes tokens. You do not set the lifetime. |

## 3. The gateway pattern: IBM ContextForge

[IBM ContextForge](https://github.com/IBM/mcp-context-forge): Apache-2.0, release v1.0.11 (28 Sept 2026), pip `mcp-contextforge-gateway`, image `ghcr.io/ibm/mcp-context-forge`.

| Feature | Fact | Source |
|---|---|---|
| Credential | Gateway registers the upstream server and holds its credential. | README |
| Endpoint | Each virtual server has `/servers/<id>/mcp`. Clients send `Authorization: Bearer <JWT>`. | README |
| Per-user tokens | Server-scoped tokens "cannot access admin endpoints". Use the `/tokens` API in production. | [Securing](https://ibm.github.io/mcp-context-forge/manage/securing/) |
| Token expiry | `/tokens` takes `expires_in_days` (whole days, minimum 1) and `scope.server_id`. | `mcpgateway/schemas.py` at v1.0.11 (not on the docs site) |
| JWT expiry | `TOKEN_EXPIRY`: "Expiry of generated JWTs in minutes", default 10080. | [Configuration](https://ibm.github.io/mcp-context-forge/manage/configuration/) |
| Plugins | PII Filter, Deny Filter, Rate Limiter, OPA (Rego policies on tool calls). | [Plugins](https://ibm.github.io/mcp-context-forge/using/plugins/plugins/) |
| SSO | GitHub, Google, IBM Security Verify, Entra ID, Keycloak, Okta, generic OIDC. | [SSO](https://ibm.github.io/mcp-context-forge/manage/sso/) |
| On-behalf-of | Identity propagation and RFC 8693 token exchange, both opt-in. | [identity-propagation.md](https://github.com/IBM/mcp-context-forge/blob/main/docs/docs/manage/identity-propagation.md) (repo only; the docs-site page returned 404) |

Not verified: how the Rovo MCP server behaves behind ContextForge with a service credential. Atlassian lists `https://mcp.atlassian.com/v2/mcp?tools=all` as an override "for MCP gateways" and says API-token auth is optional. Test it first.

## 4. The trade-off

| | Direct OAuth (lab today) | Gateway |
|---|---|---|
| Identity at Atlassian | The user (on-behalf-of) | A service account, unless the gateway passes the user identity through |
| Shared secret | None | One, held by the gateway |
| Rights | Everything the user can do in Jira | Only the tools on the virtual server |
| Token | Client-managed | Scoped to one server, with expiry |
| PII and audit | No central point | Plugins and logs in one place |
| Running cost | Nothing to host | One more service to host, patch and secure |

## 5. How we would add it to this lab

```text
1. Run the gateway: container ghcr.io/ibm/mcp-context-forge, set JWT_SECRET_KEY and PLUGINS_ENABLED=true.
2. Register mcp.atlassian.com/v2/mcp, or the open-source mcp-atlassian server, with a service credential.
3. Keep the credential in the gateway secret store only. Never in the repo.
4. Create one virtual server with five tools: search, get issue, create issue, add comment, transition.
5. Turn on the PII Filter and Deny Filter plugins for that server.
6. Mint one server-scoped token per person through /tokens.
7. /tokens counts in days (minimum 1). For 60 minutes, set TOKEN_EXPIRY=60 and test which tokens it covers.
8. In .bob/mcp.json change only the url to https://<gateway>/servers/<id>/mcp.
9. Add one header: "Authorization": "Bearer <token>".
10. Check that calls appear in the gateway logs and that a sixth tool is refused.
```

## 6. Atlassian rate limits

The [Rovo MCP page](https://www.atlassian.com/platform/rovo-mcp) does not state limits. The Atlassian getting-started page says "credit usage is per call" and links to Rovo usage limits. We give no numbers here.
