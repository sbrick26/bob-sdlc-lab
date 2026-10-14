# mcp_server.py - lets Bob run work orders by plain words. Same rules as the web screen.
from mcp.server import MCPServer

from fieldops import assign, store

server = MCPServer("fieldops")

# customer name and phone are personal data, so they are never returned
SHOWN = ["id", "site", "equipment", "description", "priority", "status", "crew", "created"]


@server.tool()
def list_orders(site: str, status: str) -> list[dict]:
    """List work orders for a site and status, best first (lowest priority number, then oldest)."""
    orders = [o for o in store.load_orders() if o["site"] == site and o["status"] == status]
    orders.sort(key=lambda o: (o["priority"], o["created"]))
    return [dict((k, o[k]) for k in SHOWN) for o in orders]


@server.tool()
def assign_order(id: int, crew: str) -> dict:
    """Give an order to a crew. Refused for an unknown crew, a missing order or a closed order."""
    return {"ok": assign.assign_order(id, crew)}


@server.tool()
def close_order(id: int) -> dict:
    """Close an order. Refused if the order does not exist."""
    return {"ok": store.update_order(id, status="closed") is not None}


def main():
    server.run("stdio")


if __name__ == "__main__":
    main()
