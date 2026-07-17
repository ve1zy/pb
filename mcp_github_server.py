from mcp.server.fastmcp import FastMCP
from typing import List
import subprocess
import json

mcp = FastMCP("github-release-server")


@mcp.tool()
def get_commits_since_tag(tag: str) -> str:
    """Get all commits since a specific tag"""
    try:
        result = subprocess.run(
            ["git", "log", f"{tag}..HEAD", "--pretty=format:%h|%s|%an|%ad", "--date=short"],
            capture_output=True, text=True, check=True
        )
        if not result.stdout.strip():
            return "No commits found since tag " + tag
        commits = []
        for line in result.stdout.strip().split("\n"):
            parts = line.split("|")
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "message": parts[1],
                    "author": parts[2],
                    "date": parts[3]
                })
        return json.dumps(commits, ensure_ascii=False, indent=2)
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


@mcp.tool()
def get_latest_tag() -> str:
    """Get the latest git tag"""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "No tags found"


@mcp.tool()
def get_all_tags() -> str:
    """Get all git tags"""
    try:
        result = subprocess.run(
            ["git", "tag", "-l", "--sort=-v:refname"],
            capture_output=True, text=True, check=True
        )
        if not result.stdout.strip():
            return "No tags found"
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


@mcp.tool()
def create_github_release(tag: str, title: str, notes: str, draft: bool = False) -> str:
    """Create a GitHub release using gh CLI"""
    cmd = ["gh", "release", "create", tag, "--title", title, "--notes", notes]
    if draft:
        cmd.append("--draft")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return f"Release created: {tag}"
    except subprocess.CalledProcessError as e:
        return f"Error creating release: {e.stderr}"


@mcp.tool()
def get_open_pull_requests() -> str:
    """Get open pull requests"""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--json", "number,title,author,createdAt"],
            capture_output=True, text=True, check=True
        )
        prs = json.loads(result.stdout)
        if not prs:
            return "No open pull requests"
        return json.dumps(prs, ensure_ascii=False, indent=2)
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


@mcp.tool()
def get_current_branch() -> str:
    """Get current git branch"""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


if __name__ == "__main__":
    mcp.run()
