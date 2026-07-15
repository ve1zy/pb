"""
Лабораторная 33: Ассистент поддержки пользователей
RAG по FAQ + MCP для тикетов
"""

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple

CURRENT_USER = os.getenv("SUPPORT_USER", "ivanov@example.com")

# ============================================================================
# 1. RAG: индекс FAQ/документации
# ============================================================================

def load_docs() -> List[Dict]:
    docs = []
    docs_dir = Path("docs_lab33")
    if docs_dir.exists():
        for md_file in docs_dir.rglob("*.md"):
            if md_file.is_file():
                with open(md_file, "r", encoding="utf-8") as f:
                    docs.append({"source": str(md_file), "content": f.read()})
    return docs


def chunk_faq(text: str) -> List[Dict]:
    """Разбивает FAQ на блоки вопрос-ответ"""
    chunks = []
    current_q = None
    current_a_lines = []
    
    for line in text.split("\n"):
        if line.startswith("**В:"):
            if current_q:
                chunks.append({"question": current_q, "answer": "\n".join(current_a_lines).strip()})
            current_q = line.replace("**В:", "").replace("**", "").strip()
            current_a_lines = []
        elif line.startswith("**О:"):
            current_a_lines.append(line.replace("**О:", "").replace("**", "").strip())
        elif current_q:
            current_a_lines.append(line)
    
    if current_q:
        chunks.append({"question": current_q, "answer": "\n".join(current_a_lines).strip()})
    
    return chunks


def tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r'\b\w+\b', text.lower()) if len(t) > 2]


def build_index(docs: List[Dict]) -> Dict:
    chunks = []
    for doc in docs:
        for chunk in chunk_faq(doc["content"]):
            chunk["source"] = doc["source"]
            chunks.append(chunk)
    
    vocab = {}
    for chunk in chunks:
        text = chunk["question"] + " " + chunk["answer"]
        for token in tokenize(text):
            if token not in vocab:
                vocab[token] = len(vocab)
    
    n_chunks = len(chunks)
    n_words = len(vocab)
    matrix = [[0.0] * n_words for _ in range(n_chunks)]
    
    for i, chunk in enumerate(chunks):
        text = chunk["question"] + " " + chunk["answer"]
        tokens = tokenize(text)
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
# 2. MCP клиент для тикетов
# ============================================================================

_mcp_session = None
_mcp_streams = None

async def start_mcp():
    global _mcp_session, _mcp_streams
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    
    params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_support_server.py"],
        env={**os.environ, "TICKETS_FILE": "tickets.json"}
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
# 3. LLM: локальная модель для естественных ответов
# ============================================================================

_llm_model = None

def load_llm():
    """Lazy loading LLM"""
    global _llm_model
    if _llm_model is not None:
        return _llm_model
    try:
        from ctransformers import AutoModelForCausalLM
        print("📦 Загрузка LLM...", flush=True)
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


def ask_llm(prompt: str, max_tokens: int = 150) -> str:
    """Запрос к LLM"""
    model = load_llm()
    if model is None:
        return ""
    try:
        return model(prompt, max_new_tokens=max_tokens, temperature=0.3).strip()
    except Exception as e:
        return f""


def llm_make_natural(faq_answer: str, question: str) -> str:
    """LLM делает ответ из FAQ более естественным"""
    prompt = f"""Ты — дружелюбный ассистент поддержки. Перефразируй ответ, сделав его естественным и кратким.

Вопрос клиента: {question}

Ответ из базы знаний:
{faq_answer}

Твой ответ (кратко, по-человечески, 1-2 предложения):"""
    return ask_llm(prompt, max_tokens=100)


def llm_summarize_ticket(ticket_text: str) -> str:
    """LLM резюмирует тикет"""
    prompt = f"""Сделай краткое резюме тикета поддержки (2-3 предложения).

{ticket_text}

Резюме:"""
    return ask_llm(prompt, max_tokens=120)


def llm_suggest_actions(ticket_text: str, faq_context: str) -> str:
    """LLM предлагает действия по тикету"""
    prompt = f"""Тикет поддержки:
{ticket_text[:500]}

Контекст из FAQ:
{faq_context[:300]}

Предложи 2-3 конкретных действия для оператора (кратко):"""
    return ask_llm(prompt, max_tokens=120)


# ============================================================================
# 4. Ассистент
# ============================================================================

async def answer_with_context(query: str, index: Dict) -> str:
    """Отвечает на вопрос с учётом тикетов пользователя + LLM"""
    query_lower = query.lower()
    
    if query_lower.startswith("тикет") or "t-0" in query_lower:
        import re
        match = re.search(r"T-\d+", query, re.IGNORECASE)
        if match:
            ticket = await call_mcp("get_ticket", {"ticket_id": match.group(0).upper()})
            
            llm_summary = llm_summarize_ticket(ticket)
            if llm_summary and len(llm_summary) > 20:
                return f"🎫 {ticket}\n\n🤖 **Резюме (LLM):**\n_{llm_summary}_"
            return f"🎫 {ticket}"
    
    user_tickets = await call_mcp("list_tickets", {"user_email": CURRENT_USER, "status": "open"})
    
    results = retrieve(query, index, top_k=2)
    
    response = []
    
    if "📋 Найдено тикетов: 0" not in user_tickets and user_tickets.strip():
        response.append("💼 **Ваши открытые тикеты:**\n")
        response.append(user_tickets)
        response.append("")
    
    if results and results[0][1] > 0.01:
        top_chunk = results[0][0]
        top_score = results[0][1]
        
        response.append(f"📖 **Ответ из базы знаний:** (релевантность: {top_score:.2f})")
        response.append(f"**В:** {top_chunk['question']}")
        response.append(f"**О:** {top_chunk['answer']}\n")
        
        # LLM обогащает ответ
        natural = llm_make_natural(top_chunk['answer'], query)
        if natural and len(natural) > 20 and "ошибк" not in natural.lower()[:20]:
            response.append("🤖 **Ответ ассистента (LLM):**")
            response.append(f"_{natural}_\n")
        
        if len(results) > 1:
            response.append("📌 **Другие подходящие вопросы:**")
            for chunk, score in results[1:]:
                if score > 0.01:
                    response.append(f"  - {chunk['question']} ({score:.2f})")
        
        return "\n".join(response)
    
    search_result = await call_mcp("search_tickets", {"query": query})
    if "🔍 Найдено" in search_result:
        response.append("🔍 **Найдено в тикетах:**\n")
        response.append(search_result)
        return "\n".join(response)
    
    return "❓ Не нашел ответ. Попробуйте:\n- Перефразировать вопрос\n- Посмотреть FAQ (/faq)\n- Создать тикет (/ticket new)"


async def main():
    print("=" * 60)
    print(f"🛟 Ассистент поддержки CloudApp")
    print(f"👤 Пользователь: {CURRENT_USER}")
    print("=" * 60)
    
    print("\n📚 Загрузка FAQ...")
    docs = load_docs()
    print(f"   Документов: {len(docs)}")
    
    print("🔨 Построение индекса...")
    index = build_index(docs)
    print(f"   Q&A блоков: {len(index['chunks'])}")
    
    print("\n📡 Подключение к CRM (MCP)...")
    await start_mcp()
    print("   ✅ MCP подключен")
    
    print("\n" + "=" * 60)
    print("Команды:")
    print("  /help      - справка")
    print("  /faq       - показать FAQ")
    print("  /tickets   - мои тикеты")
    print("  /ticket T-001 - посмотреть тикет")
    print("  /exit      - выход")
    print("  <вопрос>   - задать вопрос")
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
                print("\n📖 Команды:")
                print("  /help          - эта справка")
                print("  /faq           - показать все вопросы FAQ")
                print("  /tickets       - мои открытые тикеты")
                print("  /ticket T-001  - посмотреть тикет + LLM-резюме")
                print("  /analyze T-001 - анализ тикета + рекомендации (LLM)")
                print("  <вопрос>       - задать вопрос (RAG + LLM + контекст)")
                print("\nПримеры:")
                print("  - Почему не работает авторизация?")
                print("  - Как оплатить подписку?")
                print("  - Ошибка 429")
                print()
                continue
            
            if user_input.lower() == "/faq":
                faq_path = Path("docs_lab33/faq.md")
                if faq_path.exists():
                    print(f"\n{faq_path.read_text(encoding='utf-8')}")
                else:
                    print("❌ FAQ не найден")
                continue
            
            if user_input.lower() == "/tickets":
                tickets = await call_mcp("list_tickets", {"user_email": CURRENT_USER})
                print(f"\n{tickets}\n")
                continue
            
            if user_input.lower().startswith("/ticket"):
                parts = user_input.split()
                if len(parts) >= 2:
                    ticket_id = parts[1].upper()
                    ticket = await call_mcp("get_ticket", {"ticket_id": ticket_id})
                    print(f"\n{ticket}\n")
                    
                    # LLM резюме
                    summary = llm_summarize_ticket(ticket)
                    if summary and len(summary) > 20:
                        print(f"🤖 **Резюме (LLM):**\n_{summary}_\n")
                else:
                    print("❌ Укажите ID тикета: /ticket T-001")
                continue
            
            if user_input.lower().startswith("/analyze"):
                import re
                parts = user_input.split()
                if len(parts) >= 2:
                    ticket_id = parts[1].upper()
                    ticket = await call_mcp("get_ticket", {"ticket_id": ticket_id})
                    
                    # Получаем контекст из FAQ
                    results = retrieve(ticket, index, top_k=1)
                    faq_context = results[0][0]['answer'] if results else ""
                    
                    print(f"\n{ticket}\n")
                    
                    # LLM анализ + действия
                    actions = llm_suggest_actions(ticket, faq_context)
                    if actions and len(actions) > 20:
                        print(f"🎯 **Рекомендуемые действия (LLM):**\n{actions}\n")
                else:
                    print("❌ Использование: /analyze T-001")
                continue
            
            # Обычный вопрос
            print(f"\n{await answer_with_context(user_input, index)}\n")
    
    except KeyboardInterrupt:
        print("\n\nДо свидания!")
    except EOFError:
        print("\n\nДо свидания!")
    finally:
        await stop_mcp()


if __name__ == "__main__":
    asyncio.run(main())
