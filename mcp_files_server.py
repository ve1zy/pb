"""
MCP-сервер для работы с файлами проекта
Инструменты: чтение, поиск, анализ, создание, изменение
"""

import asyncio
import os
import re
import subprocess
import hashlib
from pathlib import Path
from typing import List, Dict
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

server = Server("files-server")

WORK_DIR = os.getenv("WORK_DIR", ".")
EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv"}


def safe_path(path: str) -> Path:
    """Возвращает безопасный путь внутри WORK_DIR"""
    p = Path(WORK_DIR) / path
    p = p.resolve()
    work = Path(WORK_DIR).resolve()
    if not str(p).startswith(str(work)):
        raise ValueError(f"Path {path} outside work dir")
    return p


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="read_file",
            description="Прочитать содержимое файла",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к файлу"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="list_files",
            description="Список файлов в директории по расширению",
            inputSchema={
                "type": "object",
                "properties": {
                    "extension": {"type": "string", "description": "Фильтр по расширению", "default": ""},
                    "directory": {"type": "string", "description": "Поддиректория", "default": "."}
                }
            }
        ),
        Tool(
            name="search_in_files",
            description="Поиск regex-паттерна в файлах",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex-паттерн"},
                    "file_pattern": {"type": "string", "description": "Фильтр файлов (например *.py)", "default": "*"},
                    "directory": {"type": "string", "description": "Где искать", "default": "."}
                },
                "required": ["pattern"]
            }
        ),
        Tool(
            name="find_usages",
            description="Найти все использования имени (функция, класс, переменная)",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Имя для поиска"},
                    "file_pattern": {"type": "string", "default": "*.py"}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="create_file",
            description="Создать новый файл с содержимым",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к новому файлу"},
                    "content": {"type": "string", "description": "Содержимое"}
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="update_file",
            description="Заменить текст в файле (старый → новый)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к файлу"},
                    "old_text": {"type": "string", "description": "Что заменить"},
                    "new_text": {"type": "string", "description": "На что заменить"}
                },
                "required": ["path", "old_text", "new_text"]
            }
        ),
        Tool(
            name="check_invariants",
            description="Проверить файлы на соответствие правилам",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_pattern": {"type": "string", "default": "*.py"},
                    "rules": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Правила: has_docstring, has_type_hints, no_print, no_todo"
                    }
                }
            }
        ),
        Tool(
            name="get_file_info",
            description="Метаинформация о файле (размер, строки, hash)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к файлу"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="generate_diff",
            description="Сгенерировать unified diff между двумя текстами",
            inputSchema={
                "type": "object",
                "properties": {
                    "old": {"type": "string", "description": "Старый текст"},
                    "new": {"type": "string", "description": "Новый текст"},
                    "old_label": {"type": "string", "default": "old"},
                    "new_label": {"type": "string", "default": "new"}
                },
                "required": ["old", "new"]
            }
        ),
        Tool(
            name="git_log",
            description="Получить git log (для генерации changelog)",
            inputSchema={
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "description": "Количество коммитов", "default": 10}
                }
            }
        )
    ]


def _read_text(path: Path, max_bytes: int = 200_000) -> str:
    if not path.exists():
        return f"❌ File not found: {path.name}"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"❌ Cannot read: {e}"
    if len(text) > max_bytes:
        return text[:max_bytes] + f"\n... [truncated, {len(text)} bytes total]"
    return text


def _list_all_files(extension: str, directory: str = ".") -> List[Path]:
    base = safe_path(directory) if directory != "." else Path(WORK_DIR)
    files = []
    for p in base.rglob(f"*{extension}"):
        if not p.is_file():
            continue
        if any(ex in p.parts for ex in EXCLUDE_DIRS):
            continue
        files.append(p)
    return sorted(files)


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    try:
        if name == "read_file":
            path = safe_path(arguments["path"])
            return [TextContent(type="text", text=_read_text(path))]

        elif name == "list_files":
            ext = arguments.get("extension", "")
            directory = arguments.get("directory", ".")
            files = _list_all_files(ext, directory)
            if not files:
                return [TextContent(type="text", text="📭 Файлов не найдено")]
            rels = [str(f.relative_to(WORK_DIR)) for f in files[:50]]
            text = f"📂 Файлов ({ext or 'все'}): {len(files)}\n\n" + "\n".join(rels)
            if len(files) > 50:
                text += f"\n... и ещё {len(files) - 50}"
            return [TextContent(type="text", text=text)]

        elif name == "search_in_files":
            pattern = arguments["pattern"]
            file_pattern = arguments.get("file_pattern", "*")
            directory = arguments.get("directory", ".")
            try:
                regex = re.compile(pattern)
            except re.error as e:
                return [TextContent(type="text", text=f"❌ Bad regex: {e}")]

            results = []
            base = safe_path(directory) if directory != "." else Path(WORK_DIR)
            for p in base.rglob(file_pattern):
                if not p.is_file() or any(ex in p.parts for ex in EXCLUDE_DIRS):
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except:
                    continue
                for i, line in enumerate(text.split("\n"), 1):
                    if regex.search(line):
                        rel = str(p.relative_to(WORK_DIR))
                        results.append(f"{rel}:{i}: {line.strip()[:200]}")
                        if len(results) >= 50:
                            break
                if len(results) >= 50:
                    break

            if not results:
                return [TextContent(type="text", text=f"🔍 Ничего не найдено по '{pattern}'")]
            return [TextContent(type="text", text=f"🔍 Найдено: {len(results)}\n\n" + "\n".join(results))]

        elif name == "find_usages":
            name = arguments["name"]
            file_pattern = arguments.get("file_pattern", "*.py")
            # Ищем определение + использования
            pattern = rf"\b{re.escape(name)}\b"
            return await handle_call_tool("search_in_files", {
                "pattern": pattern, "file_pattern": file_pattern
            })

        elif name == "create_file":
            path = safe_path(arguments["path"])
            if path.exists():
                return [TextContent(type="text", text=f"❌ Файл уже существует: {path.name}")]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments["content"], encoding="utf-8")
            return [TextContent(type="text", text=f"✅ Создан: {path.relative_to(WORK_DIR)} ({len(arguments['content'])} байт)")]

        elif name == "update_file":
            path = safe_path(arguments["path"])
            if not path.exists():
                return [TextContent(type="text", text=f"❌ Файл не найден: {path.name}")]
            text = path.read_text(encoding="utf-8")
            old = arguments["old_text"]
            new = arguments["new_text"]
            if old not in text:
                return [TextContent(type="text", text="❌ Старый текст не найден в файле")]
            new_text = text.replace(old, new, 1)
            path.write_text(new_text, encoding="utf-8")
            # diff
            import difflib
            diff = "\n".join(difflib.unified_diff(
                text.split("\n"), new_text.split("\n"),
                fromfile=f"a/{path.name}", tofile=f"b/{path.name}", lineterm=""
            ))
            return [TextContent(type="text", text=f"✅ Обновлён: {path.relative_to(WORK_DIR)}\n\n```diff\n{diff}\n```")]

        elif name == "check_invariants":
            file_pattern = arguments.get("file_pattern", "*.py")
            rules = arguments.get("rules", ["has_docstring"])
            
            files = _list_all_files(file_pattern if file_pattern.startswith(".") else f".{file_pattern.lstrip('*.')}")
            # fallback: если file_pattern это *.py
            if not files and file_pattern == "*.py":
                files = _list_all_files(".py")
            
            issues = []
            for f in files:
                text = f.read_text(encoding="utf-8", errors="replace")
                rel = str(f.relative_to(WORK_DIR))
                
                if "has_docstring" in rules:
                    if '"""' not in text and "'''" not in text and not rel.endswith("__init__.py"):
                        issues.append(f"{rel}: нет docstring в модуле")
                
                if "has_type_hints" in rules:
                    funcs = re.findall(r"def\s+(\w+)\s*\([^)]*\)\s*:", text)
                    for fn in funcs:
                        # Простая проверка: есть ли -> в определении
                        m = re.search(rf"def\s+{fn}\s*\([^)]*\)\s*(->\s*[^:]+)?\s*:", text)
                        if m and not m.group(1):
                            issues.append(f"{rel}: функция {fn}() без type hints")
                
                if "no_print" in rules:
                    for i, line in enumerate(text.split("\n"), 1):
                        if re.search(r"\bprint\s*\(", line) and "test" not in rel and "demo" not in rel:
                            issues.append(f"{rel}:{i}: print() в production коде")
                            break
                
                if "no_todo" in rules:
                    todos = re.findall(r"TODO|FIXME|XXX", text)
                    if todos:
                        issues.append(f"{rel}: {len(todos)} TODO/FIXME")
            
            if not issues:
                return [TextContent(type="text", text=f"✅ Все {len(files)} файлов соответствуют правилам {rules}")]
            return [TextContent(type="text", text=f"⚠️ Найдено проблем: {len(issues)}\n\n" + "\n".join(issues[:30]))]

        elif name == "get_file_info":
            path = safe_path(arguments["path"])
            if not path.exists():
                return [TextContent(type="text", text=f"❌ File not found")]
            stat = path.stat()
            text = path.read_text(encoding="utf-8", errors="replace")
            h = hashlib.md5(text.encode()).hexdigest()
            return [TextContent(type="text", text=(
                f"📄 {path.relative_to(WORK_DIR)}\n"
                f"   Размер: {stat.st_size} байт\n"
                f"   Строк: {len(text.split(chr(10)))}\n"
                f"   MD5: {h}\n"
                f"   Изменён: {stat.st_mtime}"
            ))]

        elif name == "generate_diff":
            import difflib
            old = arguments["old"]
            new = arguments["new"]
            old_label = arguments.get("old_label", "old")
            new_label = arguments.get("new_label", "new")
            diff = "\n".join(difflib.unified_diff(
                old.split("\n"), new.split("\n"),
                fromfile=old_label, tofile=new_label, lineterm=""
            ))
            if not diff:
                return [TextContent(type="text", text="(нет изменений)")]
            return [TextContent(type="text", text=f"```diff\n{diff}\n```")]

        elif name == "git_log":
            n = arguments.get("n", 10)
            try:
                import git
                repo = git.Repo(WORK_DIR)
                commits = list(repo.iter_commits(max_count=n))
                lines = []
                for c in commits:
                    date = c.committed_datetime.strftime("%Y-%m-%d")
                    lines.append(f"{c.hexsha[:7]} {date} {c.summary}")
                if not lines:
                    return [TextContent(type="text", text="(пусто)")]
                return [TextContent(type="text", text="\n".join(lines))]
            except Exception as e:
                return [TextContent(type="text", text=f"❌ {e}")]

        return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
