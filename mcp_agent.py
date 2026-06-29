from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from lab15 import (
    DEFAULT_AI_MODEL,
    ControlledInvariantAgent,
    create_openrouter_model,
)


class MCPKnowledgeAgent(ControlledInvariantAgent):
    def __init__(self, name: str = "MCPKnowledgeAgent", short_limit: int = 8) -> None:
        super().__init__(name=name, short_limit=short_limit)
        self.mcp_session: Optional[ClientSession] = None

    async def connect_mcp(self) -> None:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["mcp_kb_server.py"],
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

    async def process_request_async(self, user_input: str, *, use_ai: Optional[bool] = None) -> str:
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
            return f"# {data['title']}\n\n{data['content']}\n\nТеги: {data['tags']}"

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

            enriched_input = f"{query}\n\nКонтекст:\n{context}"
            return super().process_request(enriched_input, use_ai=True)

        return super().process_request(user_input, use_ai=use_ai)


def print_help() -> None:
    print(
        "\nКоманды lab11-lab15:\n"
        "  /help                              — показать команды\n"
        "\nMCP-команды:\n"
        "  /kb <запрос>                       — поиск в базе знаний\n"
        "  /kb-get <id>                       — получить статью по ID\n"
        "  /kb-add <id> <title> <content>     — добавить статью\n"
        "  /mcp-ask <вопрос>                  — AI-ответ с контекстом из базы знаний\n"
        "  /invariants                        — показать инварианты\n"
        "  /lifecycle                         — показать жизненный цикл\n"
        "  /start [название]                  — начать задачу\n"
        "  /state                             — показать состояние FSM\n"
        "  /advance [результат]               — контролируемый переход\n"
        "  /pause /resume                     — пауза / продолжение\n"
        "  /ai on|off                         — включить или выключить AI\n"
        "  /memory                            — показать память\n"
        "  /clear                             — очистить память\n"
        "  exit                               — выйти\n"
    )


async def run_cli() -> None:
    import os
    os.environ["OPENROUTER_API_KEY"] = "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"

    agent = MCPKnowledgeAgent()

    try:
        await agent.connect_mcp()
        print("MCP (база знаний) подключена.")
    except Exception as e:
        print(f"MCP не подключена: {e}")

    try:
        agent.use_ai_model(create_openrouter_model())
        print(f"AI включён: {DEFAULT_AI_MODEL}")
    except RuntimeError:
        print("AI выключен: OPENROUTER_API_KEY не задан.")

    print("--- MCP-агент с базой знаний ---")
    print_help()

    while True:
        try:
            user_text = input("\nВы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not user_text:
            continue
        if user_text.lower() in {"exit", "выход"}:
            print("Выход.")
            break

        if user_text.startswith("/"):
            parts = user_text.split(maxsplit=1)
            cmd = parts[0].lower()

            if cmd == "/help":
                print_help()
            elif cmd == "/memory":
                print(agent.memory.describe())
            elif cmd == "/clear":
                agent.clear_history()
                print("Память очищена.")
            elif cmd == "/start":
                title = user_text[len(cmd):].strip() or "Новая задача"
                print(agent.start_task(title))
            elif cmd == "/state":
                print(agent.task.describe())
            elif cmd == "/advance":
                result = user_text[len(cmd):].strip() or None
                try:
                    answer = agent.task.advance(result)
                    agent._persist_task_state()
                    print(agent.task.describe())
                except (RuntimeError, ValueError) as exc:
                    print(exc)
            elif cmd == "/pause":
                agent.task.pause()
                agent._persist_task_state()
                print(f"Пауза на состоянии {agent.task.state.value}.")
            elif cmd == "/resume":
                agent.task.resume()
                agent._persist_task_state()
                print(agent.task.describe())
            elif cmd == "/invariants":
                print(agent.invariants.describe())
            elif cmd == "/lifecycle":
                print(agent.task.describe())
            elif cmd == "/ai":
                if len(parts) < 2 or parts[1].lower() not in {"on", "off"}:
                    print("Использование: /ai on или off")
                elif parts[1].lower() == "on":
                    try:
                        agent.use_ai_model(create_openrouter_model())
                        print(f"AI включён: {DEFAULT_AI_MODEL}")
                    except RuntimeError as exc:
                        print(f"Не удалось включить AI: {exc}")
                else:
                    agent.ai_model = None
                    agent.default_use_ai = False
                    print("AI выключен.")
            else:
                print(await agent.process_request_async(user_text))
            continue

        print(await agent.process_request_async(user_text))


if __name__ == "__main__":
    asyncio.run(run_cli())
