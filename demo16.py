from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def main():
    sp = StdioServerParameters(command=sys.executable, args=["lab16.py", "--server"])
    async with stdio_client(sp) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()

            print("=" * 55)
            print("Демо lab16: MCP-сервер базы знаний")
            print("=" * 55)

            tools = await s.list_tools()
            print(f"\nЗарегистрировано инструментов: {len(tools.tools)}")
            for t in tools.tools:
                print(f"  🔧 {t.name}: {t.description}")

            print("\n▶ kb_search(query='python')")
            r = await s.call_tool("kb_search", {"query": "python"})
            data = json.loads(r.content[0].text)
            for item in data:
                print(f"   → {item['title']} (id: {item['id']}, теги: {item['tags']})")

            print("\n▶ kb_get(id='fastapi')")
            r = await s.call_tool("kb_get", {"id": "fastapi"})
            a = json.loads(r.content[0].text)
            print(f"   Название: {a['title']}")
            print(f"   Содержание: {a['content']}")
            print(f"   Теги: {a['tags']}")

            print("\n▶ kb_add(id='docker', title='Docker', content='Платформа для контейнеризации', tags='devops')")
            r = await s.call_tool("kb_add", {"id": "docker", "title": "Docker", "content": "Платформа для контейнеризации приложений.", "tags": "devops,контейнеры"})
            print(f"   Результат: {r.content[0].text}")

            print("\n▶ kb_search(query='docker') — проверка, что добавилось")
            r = await s.call_tool("kb_search", {"query": "docker"})
            data = json.loads(r.content[0].text)
            for item in data:
                print(f"   → {item['title']} (id: {item['id']})")

            print("\n▶ kb_search(query='ai') — поиск по тегу")
            r = await s.call_tool("kb_search", {"query": "ai"})
            data = json.loads(r.content[0].text)
            for item in data:
                print(f"   → {item['title']} (id: {item['id']})")

            print("\n" + "=" * 55)
            print("✅ Все инструменты протестированы:")
            print("   kb_search  — поиск по названию, содержимому, тегам")
            print("   kb_get     — получение полной статьи")
            print("   kb_add     — добавление новой статьи")
            print("   Данные сохраняются в памяти сервера")
            print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
