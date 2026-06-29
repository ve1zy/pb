import asyncio
from mcp_agent import MCPKnowledgeAgent


async def test():
    agent = MCPKnowledgeAgent()
    await agent.connect_mcp()

    print("=== /kb python ===")
    result = await agent.process_request_async("/kb python")
    print(result)
    print()

    print("=== /kb-get fastapi ===")
    result = await agent.process_request_async("/kb-get fastapi")
    print(result)
    print()

    print('=== /kb-add testing Test "Test article content" ===')
    result = await agent.process_request_async('/kb-add testing Test "Test article content"')
    print(result)
    print()

    print("=== /kb testing ===")
    result = await agent.process_request_async("/kb testing")
    print(result)
    print()

    print("=== /kb-get nonexistent ===")
    result = await agent.process_request_async("/kb-get nonexistent")
    print(result)
    print()

    await agent.disconnect_mcp()
    print("=== Интеграция работает ===")


if __name__ == "__main__":
    asyncio.run(test())
