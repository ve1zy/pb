"""
MCP-сервер поддержки: тикеты
Предоставляет инструменты для работы с тикетами пользователей
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

server = Server("support-server")

TICKETS_FILE = os.getenv("TICKETS_FILE", "tickets.json")


def load_tickets() -> list:
    """Загружает тикеты из JSON файла"""
    path = Path(TICKETS_FILE)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tickets(tickets: list):
    """Сохраняет тикеты в JSON файл"""
    with open(TICKETS_FILE, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)


def format_ticket(t: dict, full: bool = True) -> str:
    """Форматирует тикет для вывода"""
    lines = [
        f"📋 Тикет [{t['id']}] - {t['title']}",
        f"   👤 Пользователь: {t.get('user_name', t['user'])} ({t['user']})",
        f"   📊 Статус: {t['status']} | Приоритет: {t['priority']}",
        f"   📅 Создан: {t['created']}",
        f"   🏷️  Категория: {t.get('category', 'N/A')}"
    ]
    if full and t.get("messages"):
        lines.append("   💬 Сообщения:")
        for m in t["messages"]:
            who = "👤 User" if m["from"] == "user" else "🛠️  Support"
            lines.append(f"      {who} [{m['time']}]: {m['text']}")
    return "\n".join(lines)


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="get_ticket",
            description="Получить информацию о тикете по ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "ID тикета (например T-001)"
                    }
                },
                "required": ["ticket_id"]
            }
        ),
        Tool(
            name="list_tickets",
            description="Получить список тикетов (опционально по пользователю)",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_email": {
                        "type": "string",
                        "description": "Email пользователя (опционально)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Фильтр по статусу (open, closed, in_progress)"
                    }
                }
            }
        ),
        Tool(
            name="search_tickets",
            description="Поиск тикетов по ключевым словам",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="add_ticket_message",
            description="Добавить сообщение в тикет",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "ID тикета"
                    },
                    "text": {
                        "type": "string",
                        "description": "Текст сообщения"
                    },
                    "from_user": {
                        "type": "boolean",
                        "description": "True если от пользователя, False если от поддержки",
                        "default": True
                    }
                },
                "required": ["ticket_id", "text"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    try:
        if name == "get_ticket":
            ticket_id = arguments.get("ticket_id", "")
            tickets = load_tickets()
            for t in tickets:
                if t["id"] == ticket_id:
                    return [TextContent(type="text", text=format_ticket(t, full=True))]
            return [TextContent(type="text", text=f"❌ Тикет {ticket_id} не найден")]

        elif name == "list_tickets":
            user_email = arguments.get("user_email", "")
            status = arguments.get("status", "")
            tickets = load_tickets()

            if user_email:
                tickets = [t for t in tickets if t["user"] == user_email]
            if status:
                tickets = [t for t in tickets if t["status"] == status]

            if not tickets:
                return [TextContent(type="text", text="📭 Тикетов не найдено")]

            text = f"📋 Найдено тикетов: {len(tickets)}\n\n"
            for t in tickets[:10]:
                text += format_ticket(t, full=False) + "\n\n"
            return [TextContent(type="text", text=text.strip())]

        elif name == "search_tickets":
            query = arguments.get("query", "").lower()
            if not query:
                return [TextContent(type="text", text="❌ Пустой запрос")]
            tickets = load_tickets()

            results = []
            for t in tickets:
                # ищем в title, messages, category
                haystack = f"{t['title']} {t.get('category', '')} ".lower()
                haystack += " ".join(m["text"] for m in t.get("messages", []))
                if query in haystack:
                    results.append(t)

            if not results:
                return [TextContent(type="text", text=f"🔍 По запросу '{query}' ничего не найдено")]

            text = f"🔍 Найдено по запросу '{query}': {len(results)}\n\n"
            for t in results[:5]:
                text += format_ticket(t, full=False) + "\n\n"
            return [TextContent(type="text", text=text.strip())]

        elif name == "add_ticket_message":
            ticket_id = arguments.get("ticket_id", "")
            text = arguments.get("text", "")
            from_user = arguments.get("from_user", True)

            tickets = load_tickets()
            for t in tickets:
                if t["id"] == ticket_id:
                    from datetime import datetime
                    msg = {
                        "from": "user" if from_user else "support",
                        "text": text,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    t["messages"].append(msg)
                    save_tickets(tickets)
                    who = "пользователя" if from_user else "поддержки"
                    return [TextContent(type="text", text=f"✅ Сообщение от {who} добавлено в {ticket_id}")]
            return [TextContent(type="text", text=f"❌ Тикет {ticket_id} не найден")]

        return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
