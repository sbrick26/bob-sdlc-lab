# mcp_server.py - FieldOps work orders as MCP tools (stdio)
# start with: python -m fieldops.mcp_server
from mcp.server.fastmcp import FastMCP

from fieldops import assign, store

PII_FIELDS = ("customer_name", "customer_phone")

mcp = FastMCP("fieldops")


@mcp.tool()
def list_orders(site: str, status: str) -> list[dict]:
    """List work orders for a site with the given status. Customer details are not returned."""
    return [
        {k: v for k, v in o.items() if k not in PII_FIELDS}
        for o in store.load_orders()
        if o["site"] == site and o["status"] == status
    ]


@mcp.tool()
def assign_order(id: int, crew: str) -> bool:
    """Assign a work order to a crew. False if the crew is unknown or the order is missing or closed."""
    return assign.assign_order(id, crew)


@mcp.tool()
def close_order(id: int) -> bool:
    """Close a work order. Only an assigned order can be closed; otherwise False."""
    order = store.get_order(id)
    if order is None or order["status"] != "assigned":
        return False
    store.update_order(id, status="closed")
    return True


if __name__ == "__main__":
    mcp.run(transport="stdio")
