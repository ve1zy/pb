import sys
sys.path.insert(0, '.')
from lab23 import EnhancedRAGAgent

API_KEY = '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'
agent = EnhancedRAGAgent(API_KEY)
agent.load_index()

print('Тест plain режима с новой моделью...')
result = agent.ask('Что такое event loop?', mode='plain')
answer = result['answer'][:100]
elapsed = result['elapsed']
print(f'Ответ: {answer}...')
print(f'Время: {elapsed}с')
