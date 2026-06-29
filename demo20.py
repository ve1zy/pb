from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lab20 import OrchestrationAgent


async def main():
    agent = OrchestrationAgent("DemoOrchestrator")

    print("=" * 60)
    print("Демо 20: Оркестрация нескольких MCP-серверов")
    print("=" * 60)

    # 1 — Подключение
    print("\n1️⃣  Подключение к 3 серверам...")
    try:
        await agent.connect_servers()
    except Exception as e:
        print(f"   ❌ {e}")

    print("\n2️⃣  Проверка статуса:")
    print(await agent.process_request_async("/servers"))

    # 3 — Длинный флоу: search → keywords → summarize → save
    print("\n3️⃣  Длинный флоу: /orch asyncio")
    print("    Цепочка: knowledge → processor → storage (4 шага)")
    result = await agent.orchestrate("asyncio")
    print(result)

    # 4 — Список отчётов
    print("\n4️⃣  Список отчётов: /reports")
    print(await agent.process_request_async("/reports"))

    # 5 — Лог оркестрации
    print("\n5️⃣  Лог операций: (содержимое orchestration.log)")
    if os.path.exists("orchestration.log"):
        with open("orchestration.log", encoding="utf-8") as f:
            for line in f.read().strip().splitlines():
                print(f"   {line}")

    # 6 — Отключение
    print("\n6️⃣  Отключение серверов...")
    await agent.disconnect_servers()
    print("   ✅ Отключены.")

    print("\n" + "=" * 60)
    print("ИТОГ:")
    print("  3 MCP-сервера: knowledge / processor / storage")
    print("  4-шаговый флоу: search → keywords → summarize → save")
    print("  Логирование каждого шага в storage.task_log")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
