from __future__ import annotations

import asyncio
import json
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

server = Server("processor")


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="keywords_extract",
            description="Извлечение ключевых слов из текста.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Текст для анализа"},
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="text_summarize",
            description="Сокращение текста до N слов.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Текст"},
                    "max_words": {"type": "number", "description": "Макс. слов"},
                },
                "required": ["text"],
            },
        ),
    ]


STOPWORDS = {"и", "в", "на", "с", "по", "для", "от", "из", "у", "к", "о", "за", "не", "что", "это", "как", "через", "язык"}


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None):
    args = arguments or {}

    if name == "keywords_extract":
        text = args.get("text", "")
        words = text.lower().replace(",", "").replace(".", "").replace("—", "").split()
        freq = {}
        for w in words:
            w_clean = w.strip("()\"'!?")
            if len(w_clean) > 3 and w_clean not in STOPWORDS:
                freq[w_clean] = freq.get(w_clean, 0) + 1
        sorted_kw = sorted(freq.items(), key=lambda x: -x[1])[:8]
        return [TextContent(type="text", text=json.dumps({
            "keywords": [w for w, _ in sorted_kw],
            "total_words": len(words),
            "unique_words": len(freq),
        }, ensure_ascii=False, indent=2))]

    if name == "text_summarize":
        text = args.get("text", "")
        max_words = int(args.get("max_words", 30))
        words = text.split()
        summary = " ".join(words[:max_words]) + ("..." if len(words) > max_words else "")
        return [TextContent(type="text", text=json.dumps({
            "original": len(words),
            "summary": summary,
        }, ensure_ascii=False, indent=2))]

    raise ValueError(f"Неизвестный инструмент: {name}")


async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
