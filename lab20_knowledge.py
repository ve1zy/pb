from __future__ import annotations

import asyncio
import json
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

server = Server("knowledge")

kb_store = {
    "python": {"title": "Python", "content": "Python — высокоуровневый язык программирования. Используется для веба, AI, автоматизации.", "tags": "язык,ai"},
    "fastapi": {"title": "FastAPI", "content": "FastAPI — веб-фреймворк для Python с async, автодокументацией и Pydantic.", "tags": "фреймворк,веб"},
    "mcp": {"title": "Model Context Protocol", "content": "MCP — протокол интеграции LLM с внешними инструментами через единый интерфейс.", "tags": "протокол,llm"},
    "asyncio": {"title": "Asyncio", "content": "Asyncio — библиотека для асинхронного программирования на Python через async/await.", "tags": "python,async"},
    "sqlite": {"title": "SQLite", "content": "SQLite — встраиваемая реляционная БД. Не требует сервера, данные в одном файле.", "tags": "база,данных"},
}


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="knowledge_search",
            description="Поиск статей по запросу.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"},
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None):
    args = arguments or {}
    query = args.get("query", "").lower()
    q_words = set(query.split())
    results = []
    for kid, a in kb_store.items():
        t, c = a["title"].lower(), a["content"].lower()
        if (query in kid or query in t or query in c or kid in query or t in query
                or any(w in t or w in c for w in q_words)):
            results.append(a)
    return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]


async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
