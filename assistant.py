"""
Лабораторная 31: Ассистент разработчика
RAG по README + docs/ + MCP для git + /help команда
"""

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple

# ============================================================================
# 1. RAG: индекс README + docs/
# ============================================================================

def load_docs() -> List[Dict]:
    """Загружает README и docs/"""
    docs = []
    
    if os.path.exists("README.md"):
        with open("README.md", "r", encoding="utf-8") as f:
            docs.append({"source": "README.md", "content": f.read()})
    
    docs_dir = Path("docs_lab21")
    if docs_dir.exists():
        for md_file in docs_dir.rglob("*.md"):
            if md_file.is_file():
                with open(md_file, "r", encoding="utf-8") as f:
                    rel = str(md_file.relative_to("."))
                    docs.append({"source": rel, "content": f.read()})
    
    return docs


def chunk_text(text: str, chunk_size: int = 500) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks


def tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r'\b\w+\b', text.lower()) if len(t) > 2]


def build_index(docs: List[Dict]) -> Dict:
    """Строит TF-IDF индекс"""
    chunks = []
    for doc in docs:
        for chunk in chunk_text(doc["content"]):
            chunks.append({"source": doc["source"], "content": chunk})
    
    vocab = {}
    for chunk in chunks:
        for token in tokenize(chunk["content"]):
            if token not in vocab:
                vocab[token] = len(vocab)
    
    n_chunks = len(chunks)
    n_words = len(vocab)
    matrix = [[0.0] * n_words for _ in range(n_chunks)]
    
    for i, chunk in enumerate(chunks):
        tokens = tokenize(chunk["content"])
        if not tokens:
            continue
        for token in tokens:
            if token in vocab:
                matrix[i][vocab[token]] += 1
        for j in range(n_words):
            matrix[i][j] /= len(tokens)
    
    idf = {}
    for word, idx in vocab.items():
        df = sum(1 for i in range(n_chunks) if matrix[i][idx] > 0)
        idf[word] = (n_chunks + 1) / (df + 1)
    
    for i in range(n_chunks):
        for j in range(n_words):
            word = list(vocab.keys())[list(vocab.values()).index(j)]
            matrix[i][j] *= idf[word]
    
    return {"chunks": chunks, "vocab": vocab, "matrix": matrix, "idf": idf}


def retrieve(query: str, index: Dict, top_k: int = 2) -> List[Tuple[Dict, float]]:
    """Поиск релевантных чанков"""
    chunks = index["chunks"]
    vocab = index["vocab"]
    matrix = index["matrix"]
    idf = index["idf"]
    
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    
    n_words = len(vocab)
    query_vec = [0.0] * n_words
    for token in query_tokens:
        if token in vocab:
            query_vec[vocab[token]] += 1
    for j in range(n_words):
        word = list(vocab.keys())[list(vocab.values()).index(j)]
        if word in idf:
            query_vec[j] *= idf[word]
        query_vec[j] /= max(len(query_tokens), 1)
    
    def cosine(a, b):
        dot = sum(x*y for x, y in zip(a, b))
        na = sum(x*x for x in a) ** 0.5
        nb = sum(x*x for x in b) ** 0.5
        return dot / (na * nb) if na > 0 and nb > 0 else 0.0
    
    scores = [(chunks[i], cosine(query_vec, matrix[i])) for i in range(len(chunks))]
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


# ============================================================================
# 2. MCP клиент для вызова git-инструментов
# ============================================================================

_mcp_session = None
_mcp_streams = None

async def start_mcp():
    """Запускает MCP-сервер и возвращает сессию"""
    global _mcp_session, _mcp_streams
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    
    params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_git_server.py"],
        env={**os.environ, "WORK_DIR": "."}
    )
    
    _mcp_streams = stdio_client(params)
    read, write = await _mcp_streams.__aenter__()
    _mcp_session = ClientSession(read, write)
    await _mcp_session.__aenter__()
    await _mcp_session.initialize()
    return _mcp_session


async def stop_mcp():
    """Останавливает MCP-сессию"""
    global _mcp_session, _mcp_streams
    if _mcp_session:
        await _mcp_session.__aexit__(None, None, None)
        _mcp_session = None
    if _mcp_streams:
        await _mcp_streams.__aexit__(None, None, None)
        _mcp_streams = None


async def call_mcp(tool_name: str, arguments: dict = None) -> str:
    """Вызывает MCP-инструмент и возвращает текст результата"""
    if arguments is None:
        arguments = {}
    if _mcp_session is None:
        await start_mcp()
    result = await _mcp_session.call_tool(tool_name, arguments)
    if result.content:
        return result.content[0].text
    return ""


# ============================================================================
# 3. Ассистент с /help
# ============================================================================

def find_project_structure() -> str:
    """Описание структуры проекта"""
    structure = {
        "README.md": "Главный файл с описанием проекта",
        "docs_lab21/": "Документация (Python async, Docker, FastAPI, и т.д.)",
        "lab1.py ... lab30_server.py": "Лабораторные работы",
        "index_lab21.json": "TF-IDF индекс для RAG",
        "mcp_server.py": "MCP-сервер (calculator, greet)",
        "mcp_git_server.py": "MCP-сервер (git_branch, list_files, git_diff)",
        "assistant.py": "Этот ассистент"
    }
    
    lines = ["Структура проекта:"]
    for path, desc in structure.items():
        lines.append(f"  {path} - {desc}")
    return "\n".join(lines)


async def answer_question(query: str, index: Dict) -> str:
    """Отвечает на вопрос используя RAG + MCP"""
    query_lower = query.lower()
    
    if "ветк" in query_lower or "branch" in query_lower:
        result = await call_mcp("git_branch")
        return f"📂 {result}"
    
    if "структур" in query_lower or "файл" in query_lower or "проект" in query_lower:
        structure = find_project_structure()
        files = await call_mcp("list_files", {"extension": ".py"})
        return f"📁 {structure}\n\n{files}"
    
    if "diff" in query_lower or "изменен" in query_lower or "коммит" in query_lower:
        result = await call_mcp("git_diff", {"commits": 3})
        return f"📝 {result[:1000]}"
    
    results = retrieve(query, index, top_k=2)
    
    if results and results[0][1] > 0.01:
        answer = f"🔍 Найдено в документации:\n\n"
        for chunk, score in results:
            if score > 0.01:
                answer += f"[{chunk['source']}, релевантность: {score:.2f}]\n"
                answer += f"{chunk['content'][:300]}...\n\n"
        return answer.strip()
    
    return f"❓ Не нашел ответа. Попробуй спросить о:\n- ветке git\n- структуре проекта\n- документации (Python, Docker, FastAPI, и т.д.)"


async def main():
    print("=" * 60)
    print("Ассистент разработчика (RAG + MCP)")
    print("=" * 60)
    
    print("\n📚 Загрузка документации...")
    docs = load_docs()
    print(f"   Загружено документов: {len(docs)}")
    
    print("🔨 Построение RAG-индекса...")
    index = build_index(docs)
    print(f"   Чанков: {len(index['chunks'])}")
    print(f"   Словарь: {len(index['vocab'])} слов")
    
    print("\n📡 Запуск MCP-сервера...")
    await start_mcp()
    branch_result = await call_mcp("git_branch")
    print(f"   {branch_result.split(chr(10))[0]}")
    
    print("\n" + "=" * 60)
    print("Команды:")
    print("  /help   - справка")
    print("  /git    - текущая ветка")
    print("  /files  - список файлов")
    print("  /diff   - последние изменения")
    print("  /exit   - выход")
    print("  <вопрос> - задать вопрос о проекте")
    print("=" * 60 + "\n")
    
    try:
        while True:
            user_input = input("Вы: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["/exit", "/quit"]:
                print("До свидания!")
                break
            
            if user_input.lower() == "/help":
                print("\n📖 Доступные команды:")
                print("  /help   - эта справка")
                print("  /git    - показать git-ветку (через MCP)")
                print("  /files  - список файлов проекта (через MCP)")
                print("  /diff   - последние изменения (через MCP)")
                print("  <вопрос> - задать вопрос (RAG по документации)")
                print("\nПримеры вопросов:")
                print("  - Какая сейчас ветка?")
                print("  - Какая структура проекта?")
                print("  - Что такое asyncio?")
                print("  - Как использовать Docker?")
                print()
                continue
            
            if user_input.lower() == "/git":
                print(f"\n{await answer_question('git branch', index)}\n")
                continue
            
            if user_input.lower() == "/files":
                print(f"\n{await answer_question('структура проекта файлы', index)}\n")
                continue
            
            if user_input.lower() == "/diff":
                print(f"\n{await answer_question('diff изменения', index)}\n")
                continue
            
            print(f"\n{await answer_question(user_input, index)}\n")
    
    except KeyboardInterrupt:
        print("\n\nДо свидания!")
    except EOFError:
        print("\n\nДо свидания!")
    finally:
        await stop_mcp()


if __name__ == "__main__":
    asyncio.run(main())
