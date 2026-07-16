"""
Лабораторная 34: Ассистент для работы с файлами проекта (с LLM-агентом)
MCP-инструменты: чтение, поиск, анализ, создание, изменение
+ LLM-агент для принятия решений
"""

import asyncio
import os
import re
import sys
import json
from pathlib import Path


# ============================================================================
# 1. LLM: локальная модель для AI-агента
# ============================================================================

_llm_model = None

def load_llm():
    global _llm_model
    if _llm_model is not None:
        return _llm_model
    try:
        from ctransformers import AutoModelForCausalLM
        print("📦 Загрузка LLM (TinyLlama)...", flush=True)
        _llm_model = AutoModelForCausalLM.from_pretrained(
            "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
            model_file="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
            model_type="llama"
        )
        print("✅ LLM загружена", flush=True)
        return _llm_model
    except Exception as e:
        print(f"⚠️ LLM недоступна: {e}", flush=True)
        return None


def ask_llm(prompt: str, max_tokens: int = 200) -> str:
    model = load_llm()
    if model is None:
        return ""
    try:
        return model(prompt, max_new_tokens=max_tokens, temperature=0.2).strip()
    except Exception as e:
        return f""


# ============================================================================
# 2. AI-агент: выбирает инструменты по задаче
# ============================================================================

AVAILABLE_TOOLS = [
    {"name": "read_file", "args": "path", "desc": "прочитать файл"},
    {"name": "list_files", "args": "extension, directory", "desc": "список файлов"},
    {"name": "search_in_files", "args": "pattern, file_pattern, directory", "desc": "поиск regex"},
    {"name": "find_usages", "args": "name, file_pattern", "desc": "найти использования"},
    {"name": "create_file", "args": "path, content", "desc": "создать файл"},
    {"name": "update_file", "args": "path, old_text, new_text", "desc": "заменить текст"},
    {"name": "check_invariants", "args": "file_pattern, rules", "desc": "проверить правила"},
    {"name": "get_file_info", "args": "path", "desc": "инфо о файле"},
    {"name": "generate_diff", "args": "old, new, old_label, new_label", "desc": "создать diff"},
    {"name": "git_log", "args": "n", "desc": "история коммитов"},
]


TOOLS_DESC = "\n".join(
    f"- {t['name']}({t['args']}): {t['desc']}"
    for t in AVAILABLE_TOOLS
)


def agent_plan(task: str) -> dict:
    """LLM решает какой инструмент вызвать"""
    prompt = f"""Ты — AI-агент для работы с файлами. У тебя есть инструменты:

{TOOLS_DESC}

Задача пользователя: {task}

Выбери ОДИН наиболее подходящий инструмент. Ответь СТРОГО в формате JSON:
{{"tool": "имя", "args": {{"param": "value"}}}}

Если задача про поиск использований — используй find_usages.
Если про проверку файлов — check_invariants.
Если про создание changelog — сначала git_log, потом create_file.

JSON:"""
    
    resp = ask_llm(prompt, max_tokens=100)
    
    # Парсим JSON из ответа LLM
    try:
        # Ищем JSON в ответе
        match = re.search(r'\{[^{}]*"tool"[^{}]*\}', resp)
        if match:
            return json.loads(match.group(0))
    except (json.JSONDecodeError, AttributeError):
        pass
    
    # Fallback: попробуем весь ответ
    try:
        return json.loads(resp)
    except:
        pass
    
    return {"tool": "search_in_files", "args": {"pattern": task}}


def agent_interpret(task: str, tool_name: str, tool_result: str) -> str:
    """LLM интерпретирует результат и формулирует ответ"""
    prompt = f"""Ты — AI-ассистент. Пользователь задал вопрос и ты вызвал инструмент.

Вопрос: {task}
Инструмент: {tool_name}
Результат: {tool_result[:800]}

Дай краткий понятный ответ пользователю (2-3 предложения):"""
    
    return ask_llm(prompt, max_tokens=150)


async def ai_agent(task: str) -> str:
    """AI-агент: планирует → вызывает → интерпретирует"""
    if load_llm() is None:
        return "❌ LLM недоступна. Используйте команды (/find, /search, /check)"
    
    # Шаг 1: план
    plan = agent_plan(task)
    tool = plan.get("tool", "")
    args = plan.get("args", {})
    
    if not tool or tool not in [t["name"] for t in AVAILABLE_TOOLS]:
        # Fallback — поиск
        tool = "search_in_files"
        args = {"pattern": task, "file_pattern": "*.py"}
    
    # Шаг 2: вызов
    try:
        result = await call_mcp(tool, args)
    except Exception as e:
        result = f"❌ Ошибка: {e}"
    
    # Шаг 3: интерпретация
    interpretation = agent_interpret(task, tool, result)
    
    response = f"🤖 **План агента:** `{tool}({args})`\n\n"
    response += f"📊 **Результат:**\n{result[:1000]}\n\n"
    if interpretation and len(interpretation) > 10 and "ошибк" not in interpretation.lower()[:20]:
        response += f"💬 **Ответ ассистента:**\n{interpretation}"
    return response


# ============================================================================
# 3. MCP клиент
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
    print("=" * 60)
    print("\n💡 Можно писать задачу на естественном языке — AI-агент сам выберет инструмент")
    print("   Примеры: 'найди где используется ctransformers'")
    print("            'проверь все файлы на docstring'")
    print("            'сгенерируй changelog'")
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
                print("\n📋 Доступные команды:")
                for cmd, (desc, _, args) in SCENARIOS.items():
                    print(f"  {cmd} {args:<30} - {desc}")
                print("\n🤖 AI-агент (по умолчанию):")
                print("  Пишите задачу на естественном языке — LLM выберет инструмент")
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
                # AI-агент режим
                print(f"\n🤖 AI-агент обрабатывает: '{user_input}'\n")
                result = await ai_agent(user_input)
                print(f"{result}\n")
    
    except KeyboardInterrupt:
        print("\n\nДо свидания!")
    except EOFError:
        print("\n\nДо свидания!")
    finally:
        await stop_mcp()


if __name__ == "__main__":
    asyncio.run(main())
