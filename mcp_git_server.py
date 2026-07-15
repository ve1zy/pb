"""
MCP-сервер для git-операций
Предоставляет инструменты: git_branch, list_files, git_diff
"""

import asyncio
import subprocess
import os
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool
from mcp.server.stdio import stdio_server

server = Server("git-server")

WORK_DIR = os.getenv("WORK_DIR", ".")


def run_git(cmd: str) -> str:
    """Выполняет git-команду и возвращает результат"""
    try:
        result = subprocess.run(
            f"git {cmd}",
            shell=True,
            cwd=WORK_DIR,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"Error: {result.stderr.strip()}"
    except Exception as e:
        return f"Error: {str(e)}"


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="git_branch",
            description="Получить текущую git-ветку и список всех веток",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="list_files",
            description="Получить список файлов в проекте (по расширению)",
            inputSchema={
                "type": "object",
                "properties": {
                    "extension": {
                        "type": "string",
                        "description": "Фильтр по расширению (например .py, .md)",
                        "default": ""
                    }
                }
            }
        ),
        Tool(
            name="git_diff",
            description="Получить diff недавних изменений (последние N коммитов)",
            inputSchema={
                "type": "object",
                "properties": {
                    "commits": {
                        "type": "integer",
                        "description": "Количество последних коммитов",
                        "default": 1
                    }
                }
            }
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "git_branch":
        current = run_git("rev-parse --abbrev-ref HEAD")
        all_branches = run_git("branch -a")
        return [{
            "type": "text",
            "text": f"Текущая ветка: {current}\n\nВсе ветки:\n{all_branches}"
        }]

    elif name == "list_files":
        ext = arguments.get("extension", "")
        try:
            files = []
            for path in Path(WORK_DIR).rglob(f"*{ext}"):
                if path.is_file() and "__pycache__" not in str(path) and ".git" not in str(path):
                    files.append(str(path.relative_to(WORK_DIR)))
            file_list = "\n".join(sorted(files)[:50])
            return [{
                "type": "text",
                "text": f"Файлы ({ext or 'все'}):\n{file_list}\n\nВсего: {len(files)}"
            }]
        except Exception as e:
            return [{"type": "text", "text": f"Error: {str(e)}"}]

    elif name == "git_diff":
        commits = arguments.get("commits", 1)
        diff = run_git(f"diff HEAD~{commits}..HEAD")
        log = run_git(f"log --oneline -{commits}")
        return [{
            "type": "text",
            "text": f"Последние {commits} коммитов:\n{log}\n\nDiff:\n{diff[:2000]}"
        }]

    return [{"type": "text", "text": f"Unknown tool: {name}"}]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
