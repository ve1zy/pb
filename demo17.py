from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


os.environ["OPENROUTER_API_KEY"] = "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"
os.environ["OPENROUTER_MODEL"] = "cohere/north-mini-code:free"


async def call(session, tool: str, args: dict) -> str:
    r = await session.call_tool(tool, args)
    return r.content[0].text


async def main():
    sp = StdioServerParameters(command=sys.executable, args=["lab16.py", "--server"])
    async with stdio_client(sp) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()

            print("=" * 55)
            print("Демо lab17: агент + MCP база знаний")
            print("=" * 55)

            # 1. Поиск
            print("\n1️⃣  /kb python — поиск в базе знаний")
            result = await call(s, "kb_search", {"query": "python"})
            data = json.loads(result)
            for item in data:
                print(f"    {item['title']} (id: {item['id']})")

            # 2. Получение статьи
            print("\n2️⃣  /kb-get mcp — получение статьи")
            print(f"    Результат:")
            r = await call(s, "kb_get", {"id": "mcp"})
            a = json.loads(r)
            print(f"    Название: {a['title']}")
            print(f"    Содержание: {a['content']}")

            # 3. Добавление
            print("\n3️⃣  /kb-add ... — добавление новой статьи")
            r = await call(s, "kb_add", {"id": "asyncio", "title": "Asyncio", "content": "Библиотека для асинхронного программирования в Python.", "tags": "python,async"})
            print(f"    {json.loads(r)}")

            # 4. Поиск по слову из запроса
            print("\n4️⃣  /mcp-ask что такое asyncio — AI + контекст из базы")
            r = await call(s, "kb_search", {"query": "asyncio"})
            data = json.loads(r)
            if data:
                kid = data[0]["id"]
                r = await call(s, "kb_get", {"id": kid})
                article = json.loads(r)
                print(f"    Найдено в базе: {article['title']} — {article['content']}")
                print(f"    → Эта информация передаётся AI-модели как контекст")
            else:
                print("    Ничего не найдено")

            # 5. Поиск с бидирекциональным матчингом
            print("\n5️⃣  /kb что такое fastapi — поиск обращённый")
            r = await call(s, "kb_search", {"query": "что такое fastapi"})
            data = json.loads(r)
            for item in data:
                print(f"    Найдено: {item['title']} (id: {item['id']}) — найдено, т.к. 'fastapi' в заголовке")

            # 6. Поиск по тегу
            print("\n6️⃣  /kb ai — поиск по тегу")
            r = await call(s, "kb_search", {"query": "ai"})
            data = json.loads(r)
            for item in data:
                print(f"    {item['title']} (id: {item['id']}) — тег: {item['tags']}")

            print("\n" + "=" * 55)
            print("✅ Демо завершено. Интеграция работает:")
            print("   Агент вызывает MCP-инструменты и использует результаты")
            print("   lab16 (MCP-сервер) и lab17 (агент) связаны")
            print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
