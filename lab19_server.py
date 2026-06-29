from __future__ import annotations

import asyncio
import json
import os
import time

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server


kb_store = {
    "python": {
        "title": "Python",
        "content": "Python — высокоуровневый язык программирования с динамической типизацией. Используется для веб-разработки, анализа данных, AI и автоматизации. Имеет большое сообщество и множество библиотек.",
        "source": "local",
    },
    "fastapi": {
        "title": "FastAPI",
        "content": "FastAPI — современный веб-фреймворк для Python. Поддерживает асинхронность, автоматическую генерацию OpenAPI-документации и валидацию данных через Pydantic. Высокая производительность сравнима с Node.js и Go.",
        "source": "local",
    },
    "mcp": {
        "title": "Model Context Protocol",
        "content": "MCP — открытый протокол для интеграции LLM-агентов с внешними инструментами. Позволяет агентам вызывать функции, читать файлы, работать с базами данных через единый интерфейс.",
        "source": "local",
    },
    "asyncio": {
        "title": "Asyncio",
        "content": "Asyncio — библиотека Python для асинхронного программирования. Позволяет писать конкурентный код с помощью async/await. Используется для высоконагруженных I/O приложений.",
        "source": "local",
    },
}

server = Server("pipeline")


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="search",
            description="Поиск статей по запросу. Возвращает список найденных статей с заголовком и содержимым.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"},
                    "max_results": {"type": "number", "description": "Макс. количество результатов (по умолч. 3)"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="summarize",
            description="Суммаризация текста. Сокращает текст до указанного количества слов.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Текст для суммаризации"},
                    "max_words": {"type": "number", "description": "Максимум слов в саммари (по умолч. 30)"},
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="save_to_file",
            description="Сохраняет текст в файл. Возвращает путь к сохранённому файлу.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Имя файла (с расширением)"},
                    "content": {"type": "string", "description": "Содержимое файла"},
                },
                "required": ["filename", "content"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None):
    args = arguments or {}

    if name == "search":
        query = args.get("query", "").lower()
        max_results = int(args.get("max_results", 3))
        q_words = set(query.split())

        results = []
        for kid, article in kb_store.items():
            title_l = article["title"].lower()
            content_l = article["content"].lower()
            if (query in kid or query in title_l or query in content_l
                    or kid in query or title_l in query
                    or any(w in title_l or w in content_l for w in q_words)):
                results.append(article)
                if len(results) >= max_results:
                    break

        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]

    if name == "summarize":
        text = args.get("text", "")
        max_words = int(args.get("max_words", 30))

        words = text.split()
        if len(words) <= max_words:
            summary = text
        else:
            summary = " ".join(words[:max_words]) + "..."

        return [TextContent(type="text", text=json.dumps({
            "original_length": len(words),
            "summary": summary,
        }, ensure_ascii=False, indent=2))]

    if name == "save_to_file":
        filename = args.get("filename", "output.txt")
        content = args.get("content", "")

        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

        full_path = os.path.abspath(filename)
        return [TextContent(type="text", text=json.dumps({
            "status": "ok",
            "filename": filename,
            "path": full_path,
            "size_bytes": len(content.encode("utf-8")),
        }, ensure_ascii=False, indent=2))]

    raise ValueError(f"Неизвестный инструмент: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
