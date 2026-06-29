from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import time

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server


DB_PATH = "scheduler.db"


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            interval_seconds REAL,
            delay_seconds REAL,
            next_run REAL NOT NULL,
            created_at REAL NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT NOT NULL,
            executed_at REAL NOT NULL,
            result TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _load_active():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, description, interval_seconds, delay_seconds, next_run FROM schedules WHERE active=1")
    rows = c.fetchall()
    conn.close()
    return rows


def _add_schedule(sid: str, desc: str, interval: float | None, delay: float | None, next_run: float):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = time.time()
    c.execute("INSERT OR REPLACE INTO schedules (id, description, interval_seconds, delay_seconds, next_run, created_at, active) VALUES (?, ?, ?, ?, ?, ?, 1)",
              (sid, desc, interval, delay, next_run, now))
    conn.commit()
    conn.close()


def _cancel_schedule(sid: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE schedules SET active=0 WHERE id=? AND active=1", (sid,))
    ok = c.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def _save_result(sid: str, result: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO results (schedule_id, executed_at, result) VALUES (?, ?, ?)",
              (sid, time.time(), result))
    conn.commit()
    conn.close()


def _get_summary() -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM schedules WHERE active=1")
    active_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM results")
    total_runs = c.fetchone()[0]
    c.execute("""
        SELECT s.id, s.description, COUNT(r.id) as runs, MAX(r.executed_at) as last_run
        FROM schedules s LEFT JOIN results r ON s.id = r.schedule_id
        WHERE s.active=1
        GROUP BY s.id ORDER BY s.created_at DESC
    """)
    rows = c.fetchall()
    conn.close()
    lines = [f"Активных расписаний: {active_count}", f"Всего выполнений: {total_runs}"]
    for sid, desc, runs, last in rows:
        last_str = time.strftime("%H:%M:%S", time.localtime(last)) if last else "никогда"
        lines.append(f"  - {sid}: {desc} (выполнено: {runs}, последний раз: {last_str})")
    return "\n".join(lines)


server = Server("scheduler")
_active_tasks: dict[str, asyncio.Task] = {}
_scheduler_task: asyncio.Task | None = None


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="schedule_create",
            description="Создать отложенное или периодическое задание.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Уникальный ID задания"},
                    "description": {"type": "string", "description": "Описание задания"},
                    "delay_seconds": {"type": "number", "description": "Через сколько секунд выполнить (для одноразовых)"},
                    "interval_seconds": {"type": "number", "description": "Интервал в секундах (для периодических)"},
                },
                "required": ["id", "description"],
            },
        ),
        Tool(
            name="schedule_list",
            description="Показать все активные расписания.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="schedule_cancel",
            description="Отменить задание по ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "ID задания"},
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="reminder_summary",
            description="Получить сводку по всем заданиям и выполненным работам.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None):
    args = arguments or {}

    if name == "schedule_create":
        sid = args["id"]
        desc = args["description"]
        delay = args.get("delay_seconds")
        interval = args.get("interval_seconds")

        if delay is not None and interval is not None:
            return [TextContent(type="text", text="Ошибка: укажи delay_seconds ИЛИ interval_seconds, не оба.")]

        now = time.time()
        if interval is not None:
            next_run = now + interval
        elif delay is not None:
            next_run = now + delay
        else:
            next_run = now

        _add_schedule(sid, desc, interval, delay, next_run)
        kind = "каждые" if interval else "через"
        val = interval if interval else delay
        return [TextContent(type="text", text=json.dumps({
            "status": "ok", "id": sid, "kind": kind, "seconds": val,
            "next_run": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_run)),
        }, ensure_ascii=False))]

    if name == "schedule_list":
        rows = _load_active()
        items = []
        for sid, desc, interval, delay, next_run in rows:
            kind = "каждые" if interval else "через"
            val = interval if interval else delay
            items.append({
                "id": sid, "description": desc, "kind": kind, "seconds": val,
                "next_run": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_run)),
            })
        return [TextContent(type="text", text=json.dumps(items, ensure_ascii=False, indent=2))]

    if name == "schedule_cancel":
        ok = _cancel_schedule(args["id"])
        if ok:
            t = _active_tasks.pop(args["id"], None)
            if t and not t.done():
                t.cancel()
            return [TextContent(type="text", text=json.dumps({"status": "ok", "id": args["id"]}, ensure_ascii=False))]
        return [TextContent(type="text", text=json.dumps({"status": "error", "message": "Задание не найдено"}, ensure_ascii=False))]

    if name == "reminder_summary":
        return [TextContent(type="text", text=_get_summary())]

    raise ValueError(f"Неизвестный инструмент: {name}")


async def _execute_task(sid: str, desc: str):
    result = f"✅ [{time.strftime('%H:%M:%S')}] {desc}"
    _save_result(sid, result)


async def _scheduler_loop():
    """Фоновый планировщик: проверяет каждую секунду, запускает просроченные задачи."""
    while True:
        try:
            now = time.time()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, description, interval_seconds, next_run FROM schedules WHERE active=1 AND next_run <= ?", (now,))
            due = c.fetchall()
            for sid, desc, interval, next_run in due:
                await _execute_task(sid, desc)
                if interval and interval > 0:
                    new_next = next_run + interval
                    c.execute("UPDATE schedules SET next_run=? WHERE id=?", (new_next, sid))
                else:
                    c.execute("UPDATE schedules SET active=0 WHERE id=?", (sid,))
            conn.commit()
            conn.close()
        except Exception:
            pass
        await asyncio.sleep(1)


async def main():
    _init_db()
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    print("[scheduler] started", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
