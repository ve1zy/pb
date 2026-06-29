from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def call(session, tool: str, args: dict) -> str:
    r = await session.call_tool(tool, args)
    return r.content[0].text


async def main():
    sp = StdioServerParameters(command=sys.executable, args=["lab19_server.py"])
    async with stdio_client(sp) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()

            print("=" * 55)
            print("Демо lab19: Композиция MCP-инструментов")
            print("=" * 55)

            tools = await s.list_tools()
            print(f"\nИнструменты ({len(tools.tools)}):")
            for t in tools.tools:
                print(f"  🔧 {t.name}")

            # ШАГ 1
            print("\n" + "-" * 55)
            print("ШАГ 1: search(query='asyncio')")
            print("-" * 55)
            r = await call(s, "search", {"query": "asyncio", "max_results": 2})
            search_data = json.loads(r)
            print(f"   Найдено статей: {len(search_data)}")
            for a in search_data:
                print(f"   • {a['title']}: {a['content'][:60]}...")
            print(f"\n   [RAW JSON]\n{r}")

            # ШАГ 2
            print("\n" + "-" * 55)
            print("ШАГ 2: summarize(text=... , max_words=30)")
            print("-" * 55)
            all_text = " ".join(f"{a['title']}: {a['content']}" for a in search_data)
            r = await call(s, "summarize", {"text": all_text, "max_words": 30})
            summary_data = json.loads(r)
            print(f"   Было слов:  {summary_data['original_length']}")
            print(f"   Саммари:    {summary_data['summary']}")
            print(f"\n   [RAW JSON]\n{r}")

            # ШАГ 3
            print("\n" + "-" * 55)
            print("ШАГ 3: save_to_file(filename='pipeline_demo.md', content=...)")
            print("-" * 55)
            ts = str(int(asyncio.get_running_loop().time()))
            filename = f"pipeline_demo_{ts}.md"
            content = f"""# Результат пайплайна

## Найденные статьи
{chr(10).join(f'- **{a["title"]}**: {a["content"]}' for a in search_data)}

## Саммари
{summary_data['summary']}

---
Pipeline: search → summarize → save_to_file
"""
            r = await call(s, "save_to_file", {"filename": filename, "content": content})
            save_data = json.loads(r)
            print(f"   Файл:    {save_data['filename']}")
            print(f"   Путь:    {save_data['path']}")
            print(f"   Размер:  {save_data['size_bytes']} байт")
            print(f"\n   [RAW JSON]\n{r}")

            # Проверка сохранённого файла
            print("\n" + "-" * 55)
            print("ПРОВЕРКА: содержимое сохранённого файла")
            print("-" * 55)
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    print(f.read())
                os.remove(filename)
                print("   (файл удалён после проверки)")
            else:
                print("   Файл не найден!")

            # Пайплайн целиком
            print("-" * 55)
            print("ПАЙПЛАЙН ЦЕЛИКОМ: pipeline(query='fastapi')")
            print("-" * 55)
            r = await call(s, "search", {"query": "fastapi", "max_results": 1})
            data = json.loads(r)
            text = " ".join(f"{a['title']}: {a['content']}" for a in data)
            r = await call(s, "summarize", {"text": text, "max_words": 20})
            summ = json.loads(r)
            r = await call(s, "save_to_file", {
                "filename": f"pipeline_fastapi_{int(asyncio.get_running_loop().time())}.md",
                "content": f"# {data[0]['title']}\n\n{summ['summary']}",
            })
            saved = json.loads(r)
            print(f"   search → summarize(20 слов) → save_to_file")
            print(f"   Результат: {saved['path']}")
            os.remove(saved['path'])

            print("\n" + "=" * 55)
            print("✅ ИТОГ:")
            print("   • Инструменты вызываются независимо")
            print("   • Данные передаются между ними (search → summarize → save)")
            print("   • Автоматическая цепочка из 3 шагов")
            print("   • Результат сохраняется в файл на диск")
            print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
