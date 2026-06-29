from __future__ import annotations

import asyncio
import json
import sys

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server


kb_store = {
    "python": {
        "title": "Python",
        "content": "Python — язык программирования, используется для AI, веба, автоматизации.",
        "tags": "язык,ai,backend",
    },
    "fastapi": {
        "title": "FastAPI",
        "content": "FastAPI — современный веб-фреймворк для Python с поддержкой async.",
        "tags": "фреймворк,веб,api",
    },
    "mcp": {
        "title": "Model Context Protocol",
        "content": "MCP — протокол для интеграции LLM с внешними инструментами и данными.",
        "tags": "протокол,llm,интеграция",
    },
}

server = Server("knowledge-base")


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="kb_search",
            description="Поиск по базе знаний по запросу",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="kb_get",
            description="Получить статью по ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "ID статьи (python, fastapi, mcp)",
                    }
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="kb_add",
            description="Добавить статью в базу знаний",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Уникальный ID"},
                    "title": {"type": "string", "description": "Название статьи"},
                    "content": {"type": "string", "description": "Содержание"},
                    "tags": {"type": "string", "description": "Теги через запятую"},
                },
                "required": ["id", "title", "content"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None):
    args = arguments or {}

    if name == "kb_search":
        query = args.get("query", "").lower()
        q_words = set(query.split())
        results = []
        for kid, article in kb_store.items():
            title_l = article["title"].lower()
            content_l = article["content"].lower()
            tags_l = article["tags"].lower()
            if (query in kid or query in title_l or query in content_l or query in tags_l
                    or kid in query or title_l in query
                    or any(w in title_l or w in content_l or w in tags_l for w in q_words)):
                results.append({"id": kid, "title": article["title"], "tags": article["tags"]})
        text = json.dumps(results, ensure_ascii=False, indent=2)
        return [TextContent(type="text", text=text)]

    if name == "kb_get":
        kid = args.get("id", "")
        article = kb_store.get(kid)
        if not article:
            return [TextContent(type="text", text=json.dumps({"error": "Статья не найдена"}, ensure_ascii=False))]
        return [TextContent(type="text", text=json.dumps(article, ensure_ascii=False, indent=2))]

    if name == "kb_add":
        kid = args.get("id", "")
        kb_store[kid] = {
            "title": args.get("title", ""),
            "content": args.get("content", ""),
            "tags": args.get("tags", ""),
        }
        return [TextContent(type="text", text=json.dumps({"status": "ok", "id": kid}, ensure_ascii=False))]

    raise ValueError(f"Неизвестный инструмент: {name}")


async def run_server():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def run_demo():
    """Демо-режим: показывает работу инструментов без MCP-клиента."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    server_params = StdioServerParameters(command=sys.executable, args=[__file__, "--server"])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("=" * 50)
            print("Лабораторная 16: MCP-сервер базы знаний")
            print("=" * 50)

            tools = await session.list_tools()
            print(f"\nЗарегистрировано инструментов: {len(tools.tools)}")
            for tool in tools.tools:
                print(f"  → {tool.name}: {tool.description}")

            print("\n--- Тест 1: kb_search(query='python') ---")
            result = await session.call_tool("kb_search", {"query": "python"})
            data = json.loads(result.content[0].text)
            for item in data:
                print(f"  Найдено: {item['title']} (id: {item['id']})")

            print("\n--- Тест 2: kb_get(id='fastapi') ---")
            result = await session.call_tool("kb_get", {"id": "fastapi"})
            article = json.loads(result.content[0].text)
            print(f"  Название: {article['title']}")
            print(f"  Содержимое: {article['content']}")
            print(f"  Теги: {article['tags']}")

            print("\n--- Тест 3: kb_add (новая статья) ---")
            result = await session.call_tool("kb_add", {
                "id": "docker",
                "title": "Docker",
                "content": "Платформа для контейнеризации приложений.",
                "tags": "devops,контейнеры",
            })
            print(f"  Результат: {result.content[0].text}")

            print("\n--- Тест 4: kb_search(query='docker') после добавления ---")
            result = await session.call_tool("kb_search", {"query": "docker"})
            data = json.loads(result.content[0].text)
            for item in data:
                print(f"  Найдено: {item['title']} (id: {item['id']})")

            print("\n✅ MCP-сервер работает корректно.")
            print("   Инструменты зарегистрированы.")
            print("   Вызовы возвращают результаты.")
            print("   Состояние сохраняется между вызовами.")


if __name__ == "__main__":
    if "--server" in sys.argv:
        asyncio.run(run_server())
    else:
        asyncio.run(run_demo())
