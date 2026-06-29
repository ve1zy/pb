from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from lab15 import ControlledInvariantAgent


class MCPOrchestrator:
    """Подключение к одному MCP-серверу через AsyncExitStack."""

    def __init__(self, name: str, script: str):
        self.name = name
        self.script = script
        self.session: Optional[ClientSession] = None
        self._stack: contextlib.AsyncExitStack = contextlib.AsyncExitStack()

    async def connect(self):
        sp = StdioServerParameters(command=sys.executable, args=[self.script])
        r, w = await self._stack.enter_async_context(stdio_client(sp))
        self.session = await self._stack.enter_async_context(ClientSession(r, w))
        await self.session.initialize()
        tools = await self.session.list_tools()
        return [t.name for t in tools.tools]

    async def disconnect(self):
        with contextlib.suppress(BaseException):
            await self._stack.aclose()

    async def call(self, tool: str, args: dict) -> str:
        if not self.session:
            return "{}"
        r = await self.session.call_tool(tool, args)
        return r.content[0].text


class OrchestrationAgent(ControlledInvariantAgent):
    """Агент-оркестратор: подключается к 3 MCP-серверам и маршрутизирует запросы."""

    def __init__(self, name: str = "OrchestrationAgent", short_limit: int = 8) -> None:
        super().__init__(name=name, short_limit=short_limit)
        self.servers: dict[str, MCPOrchestrator] = {}

    async def connect_servers(self):
        configs = [
            ("knowledge", "lab20_knowledge.py"),
            ("processor", "lab20_processor.py"),
            ("storage", "lab20_storage.py"),
        ]
        for name, script in configs:
            srv = MCPOrchestrator(name, script)
            tools = await srv.connect()
            self.servers[name] = srv
            print(f"  ✅ {name}: {', '.join(tools)}")

    async def disconnect_servers(self):
        for srv in self.servers.values():
            with contextlib.suppress(Exception):
                await srv.disconnect()

    async def call(self, server: str, tool: str, args: dict) -> str:
        srv = self.servers.get(server)
        if not srv:
            return f"Ошибка: сервер '{server}' не подключён"
        return await srv.call(tool, args)

    async def orchestrate(self, query: str) -> str:
        """Длинный флоу: search → keywords → summarize → save + log на каждом шаге."""
        log_lines = []
        report_id = f"orch_{int(asyncio.get_running_loop().time())}"

        # Шаг 1 — знание
        log_lines.append("🔍 [knowledge] knowledge_search")
        await self.call("storage", "task_log", {"event": f"search started for '{query}'", "server": "knowledge"})
        search_raw = await self.call("knowledge", "knowledge_search", {"query": query})
        data = json.loads(search_raw)
        if not data:
            await self.call("storage", "task_log", {"event": "no results", "server": "knowledge"})
            return "Ничего не найдено."

        articles_text = "\n\n".join(f"{a['title']}: {a['content']}" for a in data)
        log_lines.append(f"   Найдено: {len(data)} статей")
        await self.call("storage", "task_log", {"event": f"found {len(data)} articles", "server": "knowledge"})

        # Шаг 2 — ключевые слова
        log_lines.append("🏷️  [processor] keywords_extract")
        kw_raw = await self.call("processor", "keywords_extract", {"text": articles_text})
        kw_data = json.loads(kw_raw)
        log_lines.append(f"   Ключевые слова: {', '.join(kw_data['keywords'])}")
        await self.call("storage", "task_log", {"event": f"keywords: {kw_data['keywords']}", "server": "processor"})

        # Шаг 3 — суммаризация
        log_lines.append("📝 [processor] text_summarize")
        summ_raw = await self.call("processor", "text_summarize", {"text": articles_text, "max_words": 40})
        summ_data = json.loads(summ_raw)
        log_lines.append(f"   Суммари: {summ_data['summary']}")
        await self.call("storage", "task_log", {"event": "summarize done", "server": "processor"})

        # Шаг 4 — сохранение
        content = f"""# Исследование: {query}

## Найденные статьи
{chr(10).join(f'- **{a["title"]}**: {a["content"]}' for a in data)}

## Ключевые слова
{', '.join(kw_data['keywords'])}

## Суммари
{summ_data['summary']}

---
Создано оркестратором: knowledge → processor → storage
"""
        log_lines.append("💾 [storage] report_save")
        save_raw = await self.call("storage", "report_save", {"title": f"Исследование: {query}", "content": content})
        save_data = json.loads(save_raw)
        log_lines.append(f"   Файл: {save_data['file']}")
        await self.call("storage", "task_log", {"event": f"report saved as {save_data['file']}", "server": "storage"})

        log_lines.append(f"\n✅ Флоу завершён. Файл: {save_data['path']}")
        log_lines.append(f"   Цепочка: knowledge → processor → storage (4 шага)")
        return "\n".join(log_lines)

    async def process_request_async(self, user_input: str) -> str:
        text = user_input.strip()
        lower = text.lower()

        if lower.startswith("/orch "):
            return await self.orchestrate(text[len("/orch "):].strip())

        if lower.startswith("/search "):
            return await self.call("knowledge", "knowledge_search", {"query": text[len("/search "):].strip()})

        if lower.startswith("/keywords "):
            return await self.call("processor", "keywords_extract", {"text": text[len("/keywords "):].strip()})

        if lower.startswith("/summarize "):
            rest = text[len("/summarize "):].strip()
            parts = rest.split(maxsplit=1)
            mw = int(parts[0]) if parts[0].isdigit() else 30
            txt = parts[1] if len(parts) > 1 else parts[0]
            return await self.call("processor", "text_summarize", {"text": txt, "max_words": mw})

        if lower.startswith("/save "):
            rest = text[len("/save "):].strip()
            parts = rest.split(maxsplit=1)
            if len(parts) < 2:
                return "/save <title> <content>"
            return await self.call("storage", "report_save", {"title": parts[0], "content": parts[1]})

        if lower in {"/reports", "/list"}:
            return await self.call("storage", "report_list", {})

        if lower.startswith("/log "):
            return await self.call("storage", "task_log", {"event": text[len("/log "):], "server": "agent"})

        if lower in {"/servers", "/status"}:
            lines = ["Подключённые серверы:"]
            for name, srv in self.servers.items():
                ok = "✅" if srv.session else "❌"
                lines.append(f"  {ok} {name}")
            return "\n".join(lines)

        return super().process_request(user_input)


async def run_cli():
    agent = OrchestrationAgent()

    print("Подключение к MCP-серверам...")
    try:
        await agent.connect_servers()
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")

    print("\n" + "=" * 55)
    print("Лабораторная 20: Оркестрация MCP-серверов")
    print("=" * 55)
    print("Серверы:")
    print("  knowledge  → knowledge_search")
    print("  processor  → keywords_extract, text_summarize")
    print("  storage    → report_save, report_list, task_log")
    print("\nКоманды:")
    print("  /orch <запрос>      — полный флоу (4 шага, 3 сервера)")
    print("  /search <запрос>    — только поиск")
    print("  /keywords <текст>   — ключевые слова")
    print("  /summarize [N] <txt> — суммаризация")
    print("  /save <title> <txt> — сохранить отчёт")
    print("  /reports            — список отчётов")
    print("  /log <событие>      — запись в лог")
    print("  /servers            — статус серверов")
    print("  /start, /state      — FSM задачи")
    print("  /invariants         — инварианты")
    print("  exit                — выход")
    print("=" * 55)

    while True:
        try:
            ut = input("\nВы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break
        if not ut or ut.lower() in {"exit", "выход"}:
            break

        if ut.startswith("/"):
            p = ut.split(maxsplit=1)
            cmd = p[0].lower()
            a = p[1] if len(p) > 1 else ""

            if cmd == "/help":
                print("/orch, /search, /keywords, /summarize, /save, /reports, /log, /servers, /start, /state, /invariants, /memory, /clear")
            elif cmd == "/memory":
                print(agent.memory.describe())
            elif cmd == "/clear":
                agent.clear_history()
                print("Память очищена.")
            elif cmd == "/start":
                print(agent.start_task(a or "Новая задача"))
            elif cmd == "/state":
                print(agent.task.describe())
            elif cmd == "/advance":
                try:
                    r = agent.task.advance(a or None)
                    agent._persist_task_state()
                    print(agent.task.describe())
                except Exception as e:
                    print(e)
            elif cmd == "/invariants":
                print(agent.invariants.describe())
            else:
                print(await agent.process_request_async(ut))
            continue

        print(await agent.process_request_async(ut))


if __name__ == "__main__":
    asyncio.run(run_cli())
