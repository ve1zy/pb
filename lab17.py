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
os.environ["OPENROUTER_MODEL"] = "poolside/laguna-m.1:free"


class MCPKnowledgeAgent(ControlledInvariantAgent):
    def __init__(self, name: str = "MCPKnowledgeAgent", short_limit: int = 8) -> None:
        super().__init__(name=name, short_limit=short_limit)
        self.mcp_session: Optional[ClientSession] = None

    async def connect_mcp(self) -> None:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["lab16.py", "--server"],
        )
        self._mcp_transport = stdio_client(server_params)
        self._mcp_read, self._mcp_write = await self._mcp_transport.__aenter__()
        self.mcp_session = await ClientSession(self._mcp_read, self._mcp_write).__aenter__()
        await self.mcp_session.initialize()

    async def disconnect_mcp(self) -> None:
        if self.mcp_session:
            await self.mcp_session.__aexit__(None, None, None)
            self.mcp_session = None
        if hasattr(self, "_mcp_transport"):
            await self._mcp_transport.__aexit__(None, None, None)

    async def call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if not self.mcp_session:
            return "MCP не подключён"
        result = await self.mcp_session.call_tool(tool_name, arguments)
        text = ""
        for content in result.content:
            if hasattr(content, "text"):
                text += content.text
        return text

    async def process_request_async(self, user_input: str) -> str:
        text = user_input.strip()
        lower = text.lower()

        if lower.startswith("/kb "):
            query = text[len("/kb "):].strip()
            result = await self.call_mcp_tool("kb_search", {"query": query})
            data = json.loads(result)
            if not data:
                return "Ничего не найдено."
            lines = ["Результаты поиска по базе знаний:"]
            for item in data:
                lines.append(f"  - {item['title']} (id: {item['id']}, теги: {item['tags']})")
            return "\n".join(lines)

        if lower.startswith("/kb-add "):
            rest = text[len("/kb-add "):]
            parts = rest.split(maxsplit=2)
            if len(parts) < 3:
                return "Использование: /kb-add <id> <title> <content>"
            kid, title, content = parts
            result = await self.call_mcp_tool("kb_add", {
                "id": kid, "title": title, "content": content, "tags": "",
            })
            data = json.loads(result)
            return f"Статья '{title}' добавлена (id: {data['id']})."

        if lower.startswith("/kb-get "):
            kid = text[len("/kb-get "):].strip()
            result = await self.call_mcp_tool("kb_get", {"id": kid})
            data = json.loads(result)
            if "error" in data:
                return data["error"]
            return f"# {data['title']}\n{data['content']}\nТеги: {data['tags']}"

        if lower.startswith("/mcp-ask "):
            query = text[len("/mcp-ask "):].strip()
            kb_result = await self.call_mcp_tool("kb_search", {"query": query})
            kb_data = json.loads(kb_result)
            if kb_data:
                kid = kb_data[0]["id"]
                article = json.loads(await self.call_mcp_tool("kb_get", {"id": kid}))
                context = f"Знание из базы: {article['title']} — {article['content']}"
            else:
                context = "В базе знаний ничего не найдено."
            enriched = f"{query}\n\nКонтекст:\n{context}"
            return super().process_request(enriched, use_ai=True)

        return super().process_request(user_input)


async def run_cli():
    agent = MCPKnowledgeAgent()

    try:
        await agent.connect_mcp()
        print("✅ MCP (база знаний) подключена.")
    except Exception as e:
        print(f"❌ MCP не подключена: {e}")

    try:
        agent.use_ai_model(create_openrouter_model())
        print(f"✅ AI включён: {DEFAULT_AI_MODEL}")
    except RuntimeError:
        print("❌ AI выключен: нет OPENROUTER_API_KEY")

    print("\n" + "=" * 50)
    print("Лабораторная 17: Интеграция агента с MCP")
    print("=" * 50)
    print("MCP-команды:")
    print("  /kb <запрос>       — поиск по базе знаний")
    print("  /kb-get <id>       — получить статью")
    print("  /kb-add <id> <title> <content> — добавить статью")
    print("  /mcp-ask <вопрос>  — AI-ответ с контекстом из базы")
    print("Команды FSM (lab15):")
    print("  /start <название>  — начать задачу")
    print("  /state             — состояние задачи")
    print("  /advance           — следующий шаг")
    print("  /lifecycle         — жизненный цикл")
    print("  /pause /resume     — пауза/продолжение")
    print("  /invariants        — инварианты")
    print("  /help              — все команды")
    print("  exit               — выход")
    print("=" * 50)

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
                print("MCP: /kb, /kb-get, /kb-add, /mcp-ask | FSM: /start, /state, /advance, /lifecycle | /invariants, /memory, /clear")
            elif cmd == "/memory":
                print(agent.memory.describe())
            elif cmd == "/clear":
                agent.clear_history()
                print("Память очищена.")
            elif cmd == "/start":
                print(agent.start_task(args or "Новая задача"))
            elif cmd == "/state":
                print(agent.task.describe())
            elif cmd == "/lifecycle":
                print(agent.task.describe())
            elif cmd == "/invariants":
                print(agent.invariants.describe())
            elif cmd == "/advance":
                try:
                    result = args or None
                    answer = agent.task.advance(result)
                    agent._persist_task_state()
                    print(agent.task.describe())
                except (RuntimeError, ValueError) as exc:
                    print(exc)
            elif cmd == "/pause":
                agent.task.pause()
                agent._persist_task_state()
                print(f"Пауза на {agent.task.state.value}.")
            elif cmd == "/resume":
                agent.task.resume()
                agent._persist_task_state()
                print(agent.task.describe())
            else:
                print(await agent.process_request_async(user_text))
            continue

        print(await agent.process_request_async(user_text))


async def run_demo():
    """Демо: проверить интеграцию агента с MCP."""
    from lab15 import run_controlled_checks

    agent = MCPKnowledgeAgent()
    await agent.connect_mcp()

    print("=" * 50)
    print("Демо лабораторной 17: вызов MCP-инструментов агентом")
    print("=" * 50)

    print("\n1. Поиск в базе знаний:")
    result = await agent.process_request_async("/kb python")
    print(result)

    print("\n2. Получение статьи:")
    result = await agent.process_request_async("/kb-get fastapi")
    print(result)

    print("\n3. Добавление статьи:")
    result = await agent.process_request_async('/kb-add docker Docker "Платформа для контейнеров"')
    print(result)

    print("\n4. Проверка добавления:")
    result = await agent.process_request_async("/kb docker")
    print(result)

    print("\n5. Задача FSM:")
    print(agent.start_task("Тестовая задача"))
    print(agent.process_request("/advance план утверждён"))
    print(agent.task.describe())

    print("\n6. Инварианты:")
    print(agent.invariants.describe())

    await agent.disconnect_mcp()

    print("\n" + "=" * 50)
    print("ИТОГ:")
    print("  ✅ MCP-соединение установлено")
    print("  ✅ Инструменты базы знаний вызываются")
    print("  ✅ Результаты возвращаются и используются")
    print("  ✅ Агент (lab15) интегрирован с MCP (lab16)")
    print("=" * 50)


if __name__ == "__main__":
    if "--demo" in sys.argv:
        asyncio.run(run_demo())
    else:
        asyncio.run(run_cli())
