from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from lab15 import (
    DEFAULT_AI_MODEL,
    ControlledInvariantAgent,
    create_openrouter_model,
)


os.environ["OPENROUTER_API_KEY"] = "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"
os.environ["OPENROUTER_MODEL"] = "cohere/north-mini-code:free"


MCPServerParams = StdioServerParameters


class MCPPipelineAgent(ControlledInvariantAgent):
    """Агент с поддержкой пайплайна MCP-инструментов: search → summarize → save_to_file."""

    def __init__(self, name: str = "MCPPipelineAgent", short_limit: int = 8) -> None:
        super().__init__(name=name, short_limit=short_limit)
        self.mcp_session: Optional[ClientSession] = None

    async def connect_mcp(self) -> None:
        sp = MCPServerParams(command=sys.executable, args=["lab19_server.py"])
        self._mcp_transport = stdio_client(sp)
        self._mcp_read, self._mcp_write = await self._mcp_transport.__aenter__()
        self.mcp_session = await ClientSession(self._mcp_read, self._mcp_write).__aenter__()
        await self.mcp_session.initialize()

    async def disconnect_mcp(self) -> None:
        if self.mcp_session:
            await self.mcp_session.__aexit__(None, None, None)
            self.mcp_session = None
        if hasattr(self, "_mcp_transport"):
            await self._mcp_transport.__aexit__(None, None, None)

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        if not self.mcp_session:
            return "MCP не подключён"
        r = await self.mcp_session.call_tool(name, args)
        return r.content[0].text

    async def run_pipeline(self, query: str) -> str:
        """Пайплайн: search → summarize → save_to_file."""
        log = []

        # Шаг 1: поиск
        log.append(f"🔍 search(query='{query}')")
        search_raw = await self.call_tool("search", {"query": query, "max_results": 2})
        search_data = json.loads(search_raw)
        if not search_data:
            return "Ничего не найдено."
        log.append(f"   Найдено: {len(search_data)} статей")

        # Шаг 2: суммаризация
        all_text = "\n\n".join(f"{a['title']}: {a['content']}" for a in search_data)
        log.append(f"   Передано в summarize: {len(all_text.split())} слов")
        summary_raw = await self.call_tool("summarize", {"text": all_text, "max_words": 40})
        summary_data = json.loads(summary_raw)
        summary = summary_data["summary"]
        log.append(f"📝 summarize → {summary_data['original_length']} → {len(summary.split())} слов")

        # Шаг 3: сохранение
        ts = str(int(asyncio.get_running_loop().time()))
        filename = f"pipeline_{query.replace(' ', '_')}_{ts}.md"
        content = f"""# Результат пайплайна: {query}

## Найденные статьи
{chr(10).join(f'- **{a["title"]}**: {a["content"]}' for a in search_data)}

## Саммари
{summary}

---
Создано: pipeline search → summarize → save_to_file
"""
        save_raw = await self.call_tool("save_to_file", {"filename": filename, "content": content})
        save_data = json.loads(save_raw)
        log.append(f"💾 save_to_file → {save_data['path']} ({save_data['size_bytes']} байт)")

        log.append(f"\n✅ Пайплайн завершён. Файл: {save_data['path']}")
        return "\n".join(log)

    async def process_request_async(self, user_input: str) -> str:
        text = user_input.strip()
        lower = text.lower()

        if lower.startswith("/pipeline "):
            query = text[len("/pipeline "):].strip()
            return await self.run_pipeline(query)

        if lower.startswith("/search "):
            query = text[len("/search "):].strip()
            return await self.call_tool("search", {"query": query, "max_results": 5})

        if lower.startswith("/summarize "):
            rest = text[len("/summarize "):].strip()
            parts = rest.split(maxsplit=1)
            if len(parts) == 2 and parts[0].isdigit():
                return await self.call_tool("summarize", {"text": parts[1], "max_words": int(parts[0])})
            return await self.call_tool("summarize", {"text": rest})

        if lower.startswith("/save "):
            rest = text[len("/save "):].strip()
            parts = rest.split(maxsplit=1)
            if len(parts) < 2:
                return "Использование: /save <filename> <content>"
            return await self.call_tool("save_to_file", {"filename": parts[0], "content": parts[1]})

        return super().process_request(user_input)


async def run_cli():
    agent = MCPPipelineAgent()

    try:
        await agent.connect_mcp()
        print("✅ MCP (пайплайн) подключён.")
    except Exception as e:
        print(f"❌ MCP не подключён: {e}")

    print("\n" + "=" * 55)
    print("Лабораторная 19: Композиция MCP-инструментов")
    print("=" * 55)
    print("Инструменты:")
    print("  search      — поиск статей")
    print("  summarize   — суммаризация текста")
    print("  save_to_file — сохранение в файл")
    print("\nКоманды:")
    print("  /pipeline <запрос>    — пайплайн: search → summarize → save_to_file")
    print("  /search <запрос>      — только поиск")
    print("  /summarize [слов] <текст> — только суммаризация")
    print("  /save <файл> <текст>  — только сохранение в файл")
    print("  /start, /state        — FSM задачи")
    print("  /invariants           — инварианты")
    print("  /help                 — помощь")
    print("  exit                  — выход")
    print("=" * 55)

    while True:
        try:
            user_text = input("\nВы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break
        if not user_text or user_text.lower() in {"exit", "выход"}:
            break

        if user_text.startswith("/"):
            parts = user_text.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            if cmd == "/help":
                print("/pipeline, /search, /summarize, /save, /start, /state, /advance, /invariants, /memory, /clear, /pause, /resume")
            elif cmd == "/memory":
                print(agent.memory.describe())
            elif cmd == "/clear":
                agent.clear_history()
                print("Память очищена.")
            elif cmd == "/start":
                print(agent.start_task(args or "Новая задача"))
            elif cmd == "/state":
                print(agent.task.describe())
            elif cmd == "/advance":
                try:
                    r = agent.task.advance(args or None)
                    agent._persist_task_state()
                    print(agent.task.describe())
                except Exception as e:
                    print(e)
            elif cmd == "/pause":
                agent.task.pause()
                agent._persist_task_state()
                print(f"Пауза на {agent.task.state.value}.")
            elif cmd == "/resume":
                agent.task.resume()
                agent._persist_task_state()
                print(agent.task.describe())
            elif cmd == "/invariants":
                print(agent.invariants.describe())
            else:
                print(await agent.process_request_async(user_text))
            continue

        print(await agent.process_request_async(user_text))


if __name__ == "__main__":
    asyncio.run(run_cli())
