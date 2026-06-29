import asyncio
from mcp.server import Server
from mcp.types import Tool
from mcp.server.stdio import stdio_server


server = Server("test-server")


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="calculator",
            description="Выполняет математические вычисления",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Математическое выражение",
                    }
                },
                "required": ["expression"],
            },
        ),
        Tool(
            name="greet",
            description="Приветствует пользователя",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Имя пользователя"}
                },
                "required": ["name"],
            },
        ),
    ]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
