import asyncio
import json
import sys
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def test_mcp_tools():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_kb_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Получить список инструментов
            tools = await session.list_tools()
            print(f"Инструментов: {len(tools.tools)}")

            # 2. Вызвать kb_search
            print("\n--- kb_search(query='python') ---")
            result = await session.call_tool("kb_search", {"query": "python"})
            data = json.loads(result.content[0].text)
            print(f"Результатов: {len(data)}")
            for item in data:
                print(f"  - {item['title']} (id: {item['id']})")

            # 3. Вызвать kb_get
            print("\n--- kb_get(id='fastapi') ---")
            result = await session.call_tool("kb_get", {"id": "fastapi"})
            article = json.loads(result.content[0].text)
            print(f"Title: {article['title']}")
            print(f"Content: {article['content']}")

            # 4. Вызвать kb_add (новый инструмент)
            print("\n--- kb_add(id='docker', title='Docker', content='Docker — платформа для контейнеризации') ---")
            result = await session.call_tool("kb_add", {
                "id": "docker",
                "title": "Docker",
                "content": "Docker — платформа для контейнеризации приложений.",
                "tags": "devops,контейнеры",
            })
            status = json.loads(result.content[0].text)
            print(f"Status: {status}")

            # 5. Проверить, что новая статья появилась
            print("\n--- kb_search(query='docker') ---")
            result = await session.call_tool("kb_search", {"query": "docker"})
            data = json.loads(result.content[0].text)
            print(f"Результатов: {len(data)}")
            for item in data:
                print(f"  - {item['title']} (id: {item['id']})")

            print("\n=== Все тесты пройдены ===")


if __name__ == "__main__":
    asyncio.run(test_mcp_tools())
