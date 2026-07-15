import asyncio
import os
import sys
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

server = Server("git-server")

WORK_DIR = os.getenv("WORK_DIR", ".")

# Use GitPython to avoid subprocess issues on Windows
import git
try:
    repo = git.Repo(WORK_DIR)
except Exception as e:
    repo = None
    print(f"GitPython init error: {e}", file=sys.stderr)


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
    try:
        if name == "git_branch":
            if repo and not repo.bare:
                current = repo.active_branch.name
                all_branches = [b.name for b in repo.branches]
                text = f"Текущая ветка: {current}\n\nВсе ветки:\n" + "\n".join(all_branches)
                return [TextContent(type="text", text=text)]
            return [TextContent(type="text", text="Error: not a git repo")]

        elif name == "list_files":
            ext = arguments.get("extension", "")
            try:
                files = []
                for path in Path(WORK_DIR).rglob(f"*{ext}"):
                    if path.is_file() and "__pycache__" not in str(path) and ".git" not in str(path):
                        files.append(str(path.relative_to(WORK_DIR)))
                file_list = "\n".join(sorted(files)[:50])
                text = f"Файлы ({ext or 'все'}):\n{file_list}\n\nВсего: {len(files)}"
                return [TextContent(type="text", text=text)]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        elif name == "git_diff":
            commits = arguments.get("commits", 1)
            if repo and not repo.bare:
                try:
                    log = list(repo.iter_commits(max_count=commits))
                    log_text = "\n".join(f"{c.hexsha[:7]} {c.summary}" for c in log)

                    # Get diff between HEAD and HEAD~N
                    if len(log) >= commits:
                        diff = repo.git.diff(f"HEAD~{commits}..HEAD")
                    else:
                        diff = "(not enough commits for diff)"

                    text = f"Последние {commits} коммитов:\n{log_text}\n\nDiff:\n{diff[:2000]}"
                    return [TextContent(type="text", text=text)]
                except Exception as e:
                    return [TextContent(type="text", text=f"Error: {e}")]
            return [TextContent(type="text", text="Error: not a git repo")]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
