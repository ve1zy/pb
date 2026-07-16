"""
Лабораторная 34: Ассистент для работы с файлами проекта
MCP-инструменты: чтение, поиск, анализ, создание, изменение
"""

import asyncio
import os
import re
import sys
from pathlib import Path


# ============================================================================
# 1. MCP клиент
# ============================================================================

_mcp_session = None
_mcp_streams = None

async def start_mcp():
    global _mcp_session, _mcp_streams
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    
    params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_files_server.py"],
        env={**os.environ, "WORK_DIR": os.getcwd()}
    )
    
    _mcp_streams = stdio_client(params)
    read, write = await _mcp_streams.__aenter__()
    _mcp_session = ClientSession(read, write)
    await _mcp_session.__aenter__()
    await _mcp_session.initialize()
    return _mcp_session


async def stop_mcp():
    global _mcp_session, _mcp_streams
    if _mcp_session:
        await _mcp_session.__aexit__(None, None, None)
        _mcp_session = None
    if _mcp_streams:
        await _mcp_streams.__aexit__(None, None, None)
        _mcp_streams = None


async def call_mcp(tool_name: str, arguments: dict = None) -> str:
    if arguments is None:
        arguments = {}
    if _mcp_session is None:
        await start_mcp()
    result = await _mcp_session.call_tool(tool_name, arguments)
    if result.content:
        return result.content[0].text
    return ""


# ============================================================================
# 2. Сценарии работы с файлами
# ============================================================================

async def scenario_find_usages(component: str) -> str:
    """Сценарий 1: найти все использования компонента"""
    result = await call_mcp("find_usages", {"name": component, "file_pattern": "*.py"})
    return f"🔍 **Поиск использований `{component}`:**\n\n{result}"


async def scenario_update_docs() -> str:
    """Сценарий 2: обновить документацию на основе docstrings"""
    # Найти все .py файлы
    files_text = await call_mcp("list_files", {"extension": ".py", "directory": "."})
    if "📭" in files_text:
        return "❌ Нет .py файлов"
    
    # Извлечь имена функций и docstrings
    files_lines = files_text.split("\n")[2:]  # пропускаем заголовок
    py_files = [f.strip() for f in files_lines if f.strip() and not f.startswith("...")]
    
    # Собираем функции
    functions = []
    for path in py_files[:10]:  # лимит
        content = await call_mcp("read_file", {"path": path})
        # Простой парсинг def ... """:..."""
        for m in re.finditer(r'def\s+(\w+)\s*\([^)]*\)[^:]*:\s*\n\s*"""([^"]+)"""', content):
            func_name = m.group(1)
            docstring = m.group(2).strip().split("\n")[0]
            if not func_name.startswith("_") and len(docstring) > 5:
                functions.append((path, func_name, docstring))
    
    if not functions:
        return "❌ Не найдено функций с docstring"
    
    # Обновляем API.md
    api_content = "# API Reference\n\nАвтоматически сгенерировано ассистентом.\n\n"
    api_content += "## Функции\n\n"
    for path, name, doc in functions[:20]:
        api_content += f"### `{name}()` ({path})\n\n{doc}\n\n"
    
    result = await call_mcp("create_file", {"path": "API.md", "content": api_content})
    return f"📚 **Обновление документации:**\n\n{result}\n\nНайдено функций: {len(functions)}"


async def scenario_generate_changelog() -> str:
    """Сценарий 3: сгенерировать CHANGELOG.md из git log"""
    log = await call_mcp("git_log", {"n": 15})
    if not log or "❌" in log:
        return "❌ Не удалось получить git log"
    
    content = "# Changelog\n\nАвтоматически сгенерирован из git history.\n\n"
    content += "## Recent commits\n\n"
    content += "```\n" + log + "\n```\n"
    
    result = await call_mcp("create_file", {"path": "CHANGELOG.md", "content": content})
    return f"📝 **Генерация CHANGELOG:**\n\n{result}\n\n{log[:300]}"


async def scenario_generate_adr(title: str, decision: str) -> str:
    """Сценарий 4: сгенерировать ADR"""
    content = f"""# ADR: {title}

## Status
Proposed

## Context
{decision}

## Decision
{decision}

## Consequences
TBD
"""
    result = await call_mcp("create_file", {"path": f"docs_lab34/adr-{title.lower().replace(' ', '-')}.md", "content": content})
    return f"📋 **Создание ADR:**\n\n{result}"


async def scenario_check_invariants() -> str:
    """Сценарий 5: проверить инварианты"""
    result = await call_mcp("check_invariants", {
        "file_pattern": "*.py",
        "rules": ["has_docstring", "no_todo"]
    })
    return f"🔍 **Проверка инвариантов:**\n\n{result}"


async def scenario_search_code(query: str) -> str:
    """Сценарий 6: поиск по коду"""
    result = await call_mcp("search_in_files", {
        "pattern": query,
        "file_pattern": "*.py"
    })
    return f"🔎 **Поиск '{query}':**\n\n{result}"


# ============================================================================
# 3. Главный цикл
# ============================================================================

SCENARIOS = {
    "/find": ("Поиск использований", scenario_find_usages, "<component>"),
    "/update-docs": ("Обновить документацию", scenario_update_docs, ""),
    "/changelog": ("Сгенерировать CHANGELOG", scenario_generate_changelog, ""),
    "/adr": ("Создать ADR", scenario_generate_adr, "<title>|<decision>"),
    "/check": ("Проверить инварианты", scenario_check_invariants, ""),
    "/search": ("Поиск по коду", scenario_search_code, "<regex>"),
}


async def main():
    print("=" * 60)
    print("📁 Ассистент для работы с файлами")
    print(f"📂 Рабочая директория: {os.getcwd()}")
    print("=" * 60)
    
    print("\n📡 Подключение к MCP...")
    await start_mcp()
    print("   ✅ MCP подключен")
    
    print("\n" + "=" * 60)
    print("Команды (сценарии):")
    for cmd, (desc, _, args) in SCENARIOS.items():
        print(f"  {cmd} {args:<30} - {desc}")
    print("=" * 60 + "\n")
    
    try:
        while True:
            user_input = input("Задача: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["/exit", "/quit"]:
                print("До свидания!")
                break
            
            if user_input.lower() == "/help":
                print("\n📋 Доступные сценарии:")
                for cmd, (desc, _, args) in SCENARIOS.items():
                    print(f"  {cmd} {args:<30} - {desc}")
                print("  Примеры:")
                print("    /find ctransformers")
                print("    /search 'def.*llm'")
                print("    /adr 'Use local LLM'|'Мы выбрали ctransformers потому что...'")
                print()
                continue
            
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            if cmd in SCENARIOS:
                _, func, arg_template = SCENARIOS[cmd]
                if arg_template and not args:
                    print(f"❌ Нужны аргументы: {arg_template}")
                    continue
                
                if cmd == "/adr" and "|" in args:
                    title, decision = args.split("|", 1)
                    result = await func(title.strip(), decision.strip())
                else:
                    result = await func(args)
                print(f"\n{result}\n")
            else:
                # Свободный запрос — поиск
                result = await scenario_search_code(user_input)
                print(f"\n{result}\n")
    
    except KeyboardInterrupt:
        print("\n\nДо свидания!")
    except EOFError:
        print("\n\nДо свидания!")
    finally:
        await stop_mcp()


if __name__ == "__main__":
    asyncio.run(main())
