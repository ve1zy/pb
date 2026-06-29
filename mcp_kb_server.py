import asyncio
import json
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

server = Server("knowledge-base")

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


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="kb_search",
            description="Поиск по базе знаний. Возвращает список статей, соответствующих запросу.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос (по названию, содержимому или тегам)",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="kb_get",
            description="Получить полную статью из базы знаний по ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "ID статьи (например: python, fastapi, mcp)",
                    }
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="kb_add",
            description="Добавить новую статью в базу знаний.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Уникальный ID статьи",
                    },
                    "title": {
                        "type": "string",
                        "description": "Название статьи",
                    },
                    "content": {
                        "type": "string",
                        "description": "Содержание статьи",
                    },
                    "tags": {
                        "type": "string",
                        "description": "Теги через запятую",
                    },
                },
                "required": ["id", "title", "content"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None):
    if name == "kb_search":
        query = (arguments or {}).get("query", "").lower()
        results = []
        for kid, article in kb_store.items():
            if (query in kid or query in article["title"].lower()
                    or query in article["content"].lower() or query in article["tags"].lower()):
                results.append({"id": kid, "title": article["title"], "tags": article["tags"]})
        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]

    if name == "kb_get":
        kid = (arguments or {}).get("id", "")
        article = kb_store.get(kid)
        if not article:
            return [TextContent(type="text", text=json.dumps({"error": "Статья не найдена"}, ensure_ascii=False))]
        return [TextContent(type="text", text=json.dumps(article, ensure_ascii=False, indent=2))]

    if name == "kb_add":
        args = arguments or {}
        kid = args.get("id", "")
        kb_store[kid] = {
            "title": args.get("title", ""),
            "content": args.get("content", ""),
            "tags": args.get("tags", ""),
        }
        return [TextContent(type="text", text=json.dumps({"status": "ok", "id": kid}, ensure_ascii=False))]

    raise ValueError(f"Неизвестный инструмент: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
