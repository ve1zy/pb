from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def call(session, tool: str, args: dict) -> str:
    r = await session.call_tool(tool, args)
    return r.content[0].text


async def main():
    sp = StdioServerParameters(command=sys.executable, args=["lab18_server.py"])
    async with stdio_client(sp) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()

            print("=" * 55)
            print("Демо lab18: Планировщик и фоновые задачи")
            print("=" * 55)

            # 1. Создать напоминание
            print("\n1️⃣  Создание напоминания через 4 секунды")
            r = await call(s, "schedule_create", {"id": "remind1", "description": "Поставить чайник 🔥", "delay_seconds": 4})
            print(f"    {json.loads(r)}")

            # 2. Создать периодическое задание
            print("\n2️⃣  Создание периодического задания (каждые 6 секунд)")
            r = await call(s, "schedule_create", {"id": "metrics1", "description": "Сбор метрик CPU", "interval_seconds": 6})
            print(f"    {json.loads(r)}")

            # 3. Список
            print("\n3️⃣  Список активных заданий")
            r = await call(s, "schedule_list", {})
            data = json.loads(r)
            for item in data:
                print(f"    • {item['id']}: {item['description']} ({item['kind']} {item['seconds']}с, след.: {item['next_run']})")

            # 4. Ждём выполнение
            print("\n4️⃣  Ожидание 8 секунд (задачи выполняются)...")
            for i in range(8):
                await asyncio.sleep(1)
                print("   ", i + 1, "с", sep="")
            print("    Ожидание завершено.")

            # 5. Сводка
            print("\n5️⃣  Сводка выполненных работ")
            r = await call(s, "reminder_summary", {})
            print(f"    {r}")

            # 6. Отмена
            print("\n6️⃣  Отмена задания metrics1")
            r = await call(s, "schedule_cancel", {"id": "metrics1"})
            print(f"    {json.loads(r)}")

            # 7. Финальная сводка
            print("\n7️⃣  Финальная сводка после отмены")
            r = await call(s, "reminder_summary", {})
            print(f"    {r}")

            print("\n" + "=" * 55)
            print("✅ Демо завершено:")
            print("   • Отложенные задачи создаются и выполняются")
            print("   • Периодические задачи повторяются по расписанию")
            print("   • Результаты сохраняются в SQLite")
            print("   • Сводка агрегирует все выполнения")
            print("   • Задачи можно отменять")
            print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
