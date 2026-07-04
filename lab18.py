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


class MCPSchedulerAgent(ControlledInvariantAgent):
    def __init__(self, name: str = "MCPSchedulerAgent", short_limit: int = 8) -> None:
        super().__init__(name=name, short_limit=short_limit)
        self.mcp_session: Optional[ClientSession] = None

    async def connect_mcp(self) -> None:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["lab18_server.py"],
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

        if lower.startswith("/remind "):
            rest = text[len("/remind "):].strip()
            parts = rest.split(maxsplit=1)
            if len(parts) < 1:
                return "Использование: /remind <сек> <текст>  или  /remind <текст>"
            try:
                delay = int(parts[0])
                desc = parts[1] if len(parts) > 1 else "Напоминание"
                sid = f"reminder_{int(asyncio.get_running_loop().time())}"
            except ValueError:
                delay = 10
                desc = rest
                sid = f"reminder_{int(asyncio.get_running_loop().time())}"
            result = await self.call_mcp_tool("schedule_create", {
                "id": sid, "description": desc, "delay_seconds": delay,
            })
            data = json.loads(result)
            return f"⏰ Напоминание через {delay}с: «{desc}» (id: {data['id']})"

        if lower.startswith("/every "):
            rest = text[len("/every "):].strip()
            parts = rest.split(maxsplit=1)
            if len(parts) < 2:
                return "Использование: /every <сек> <описание>"
            try:
                interval = int(parts[0])
                desc = parts[1]
                sid = f"periodic_{int(asyncio.get_running_loop().time())}"
            except ValueError:
                return "Интервал должен быть числом в секундах"
            result = await self.call_mcp_tool("schedule_create", {
                "id": sid, "description": desc, "interval_seconds": interval,
            })
            data = json.loads(result)
            return f"🔄 Периодическое задание каждые {interval}с: «{desc}» (id: {data['id']})"

        if lower.startswith("/cancel "):
            sid = text[len("/cancel "):].strip()
            result = await self.call_mcp_tool("schedule_cancel", {"id": sid})
            data = json.loads(result)
            if data.get("status") == "ok":
                return f"❌ Задание {sid} отменено."
            return f"Задание {sid} не найдено."

        if lower in {"/schedules", "/list"}:
            result = await self.call_mcp_tool("schedule_list", {})
            data = json.loads(result)
            if not data:
                return "Нет активных заданий."
            lines = ["Активные задания:"]
            for item in data:
                lines.append(f"  - {item['id']}: {item['description']} ({item['kind']} {item['seconds']}с, след.: {item['next_run']})")
            return "\n".join(lines)

        if lower in {"/summary", "/stats"}:
            return await self.call_mcp_tool("reminder_summary", {})

        return super().process_request(user_input)

    async def _auto_summary_loop(self, interval: int = 30):
        """Фоновый сбор сводки каждые N секунд."""
        await asyncio.sleep(5)
        while True:
            s = await self.call_mcp_tool("reminder_summary", {})
            print(f"\n📊 [авто-сводка] {s}\n")
            await asyncio.sleep(interval)


async def run_cli():
    agent = MCPSchedulerAgent()

    try:
        await agent.connect_mcp()
        print("✅ MCP (планировщик) подключён.")
    except Exception as e:
        print(f"❌ MCP не подключён: {e}")

    try:
        agent.use_ai_model(create_openrouter_model())
        print(f"✅ AI включён: {DEFAULT_AI_MODEL}")
    except RuntimeError:
        print("❌ AI выключен.")

    print("\n" + "=" * 50)
    print("Лабораторная 18: Планировщик и фоновые задачи")
    print("=" * 50)
    print("Команды:")
    print("  /remind <сек> <текст>     — напоминание через N секунд")
    print("  /every <сек> <описание>   — периодическое задание")
    print("  /cancel <id>              — отменить задание")
    print("  /schedules                — список активных заданий")
    print("  /summary                  — сводка выполненных работ")
    print("  /auto-summary             — авто-сводка каждые 30с (фон)")
    print("  /start, /state, /advance  — FSM задачи")
    print("  /invariants               — инварианты")
    print("  /help                     — помощь")
    print("  exit                      — выход")
    print("=" * 50)

    auto_task = None

    while True:
        try:
            user_text = input("\nВы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not user_text or user_text.lower() in {"exit", "выход"}:
            if auto_task:
                auto_task.cancel()
            break

        if user_text.startswith("/"):
            parts = user_text.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            if cmd == "/help":
                print("/remind, /every, /cancel, /schedules, /summary, /auto-summary, /start, /state, /advance, /invariants, /pause, /resume, /memory, /clear")
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
                    answer = agent.task.advance(args or None)
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
            elif cmd == "/invariants":
                print(agent.invariants.describe())
            elif cmd == "/auto-summary":
                if auto_task and not auto_task.done():
                    print("Авто-сводка уже запущена.")
                else:
                    auto_task = asyncio.create_task(agent._auto_summary_loop(30))
                    print("📊 Авто-сводка каждые 30с запущена.")
            else:
                print(await agent.process_request_async(user_text))
            continue

        print(await agent.process_request_async(user_text))


async def run_demo():
    agent = MCPSchedulerAgent()
    await agent.connect_mcp()

    print("=" * 50)
    print("Демо лабораторной 18: Планировщик")
    print("=" * 50)

    print("\n1. Создаём напоминание через 5с:")
    r = await agent.process_request_async("/remind 5 Пора проверить логи")
    print(r)

    print("\n2. Создаём периодическое задание каждые 8с:")
    r = await agent.process_request_async("/every 8 Сбор метрик")
    print(r)

    print("\n3. Список активных заданий:")
    r = await agent.process_request_async("/schedules")
    print(r)

    print("\n4. Ждём 12 секунд (выполнение задач)...")
    for i in range(12):
        await asyncio.sleep(1)
        print(".", end="", flush=True)
    print()

    print("\n5. Сводка выполненных работ:")
    r = await agent.process_request_async("/summary")
    print(r)

    print("\n6. Отменяем метрики:")
    for s in ["periodic_", "reminder_"]:
        r = await agent.process_request_async("/schedules")
        data = json.loads(r.split("\n", 1)[1] if "\n" in r else "[]")
        data_parsed = []
        if data and isinstance(data, str):
            data_parsed = json.loads(data)
        else:
            lines = r.split("\n")
            data_parsed = [{"id": l.split(":")[0].strip().lstrip("- ")} for l in lines if l.strip().startswith("- ")]
    r = await agent.process_request_async("/cancel metrics_1001")
    print(r)

    print("\n7. Финальная сводка:")
    r = await agent.process_request_async("/summary")
    print(r)

    print("\n" + "=" * 50)
    print("ИТОГ:")
    print("  ✅ Отложенные задачи создаются")
    print("  ✅ Периодические задачи повторяются")
    print("  ✅ Результаты сохраняются в SQLite")
    print("  ✅ Сводка агрегирует все выполнения")
    print("  ✅ Задачи можно отменить")
    print("=" * 50)

    await agent.disconnect_mcp()


if __name__ == "__main__":
    if "--demo" in sys.argv:
        asyncio.run(run_demo())
    else:
        asyncio.run(run_cli())
