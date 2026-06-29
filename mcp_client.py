import asyncio
import sys
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def main():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()

            print("=== MCP соединение установлено ===")
            print(f"\nДоступные инструментов: {len(tools.tools)}")
            print("-" * 40)

            for tool in tools.tools:
                print(f"\n  Имя:        {tool.name}")
                print(f"  Описание:   {tool.description}")
                print(f"  Схема:      {tool.inputSchema}")

            print("\n=== Список инструментов успешно получен ===")


if __name__ == "__main__":
    asyncio.run(main())
