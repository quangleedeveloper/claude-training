from mcp.server import MCPServer

from app.core.prompt import MCP_SERVER_INSTRUCTIONS
from app.mcp import tools_personas

# One list of modules that each add their tools, so a new tool has a single place to
# be registered and tests can walk every tool the server really offers
TOOL_MODULES = (tools_personas,)


def build_server() -> MCPServer:
    server = MCPServer("Memorial Robot", instructions=MCP_SERVER_INSTRUCTIONS)
    for module in TOOL_MODULES:
        module.register(server)
    return server
