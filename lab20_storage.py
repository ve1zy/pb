from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

server = Server("storage")
DB_PATH = "lab20_orch.db"


def _init():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, created_at REAL)")
    conn.commit()
    conn.close()


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="report_save",
            description="Сохранить отчёт в SQLite и на диск.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Название отчёта"},
                    "content": {"type": "string", "description": "Содержимое"},
                },
                "required": ["title", "content"],
            },
        ),
        Tool(
            name="report_list",
            description="Список сохранённых отчётов.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="task_log",
            description="Запись события в лог.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event": {"type": "string", "description": "Описание события"},
                    "server": {"type": "string", "description": "Какой сервер вызвал"},
                },
                "required": ["event", "server"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None):
    args = arguments or {}

    if name == "report_save":
        title = args.get("title", "Без названия")
        content = args.get("content", "")
        now = time.time()

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO reports (title, content, created_at) VALUES (?, ?, ?)", (title, content, now))
        conn.commit()
        report_id = c.lastrowid
        conn.close()

        filename = f"report_{report_id}_{title.replace(' ', '_')[:20]}.md"
        md = f"# {title}\n\n{content}\n\n---\nСохранено: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(md)

        return [TextContent(type="text", text=json.dumps({
            "status": "ok", "report_id": report_id, "file": filename, "path": os.path.abspath(filename),
        }, ensure_ascii=False, indent=2))]

    if name == "report_list":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, title, created_at FROM reports ORDER BY id DESC")
        rows = c.fetchall()
        conn.close()
        items = [{"id": r[0], "title": r[1], "created": time.strftime("%H:%M:%S", time.localtime(r[2]))} for r in rows]
        return [TextContent(type="text", text=json.dumps(items, ensure_ascii=False, indent=2))]

    if name == "task_log":
        event = args.get("event", "")
        server_name = args.get("server", "?")
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {server_name}: {event}"
        with open("orchestration.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return [TextContent(type="text", text=json.dumps({"logged": True, "line": line}, ensure_ascii=False, indent=2))]

    raise ValueError(f"Неизвестный инструмент: {name}")


async def main():
    _init()
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
