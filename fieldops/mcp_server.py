# mcp_server.py - FieldOps tools for Bob over MCP (stdio)
from mcp.server.mcpserver import MCPServer

from fieldops import assign, store

mcp = MCPServer("fieldops")

SHOWN = ["id", "site", "equipment", "description", "priority", "status", "crew", "created"]


@mcp.tool()
def list_orders(site: str, status: str) -> list[dict]:
    """List work orders for a site and status, most urgent first (no customer data)."""
    orders = [o for o in store.load_orders() if o["site"] == site and o["status"] == status]
    orders.sort(key=lambda o: (o["priority"], o["created"]))
    return [{k: o[k] for k in SHOWN} for o in orders]


@mcp.tool()
def assign_order(id: int, crew: str) -> dict:
    """Assign an order to a crew. Refused for an unknown crew, a missing order or a closed order."""
    return {"ok": assign.assign_order(id, crew)}


@mcp.tool()
def close_order(id: int) -> dict:
    """Close an order. Refused if the order does not exist."""
    return {"ok": store.update_order(id, status="closed") is not None}


def main():
    mcp.run("stdio")


if __name__ == "__main__":
    main()
