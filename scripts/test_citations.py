import httpx
import json

print('=' * 80)
print('TEST 1 (Non-streaming): Verify Citation Format [[uuid]]')
print('=' * 80)

response = httpx.post(
    'http://localhost:8000/api/v1/chat/complete',
    json={'message': 'What is the revenue recognition policy under ASC 606?', 'top_k': 3},
    headers={'X-Impersonate-Role': 'finance'},
    timeout=120.0
)

print(f'Status: {response.status_code}')
data = response.json()
print('has_sufficient_context:', data['has_sufficient_context'])
print('Response:', data['response'])
print()
print('Citations:')
for c in data['citations']:
    print(f'  - {c["source_id"]}: {c["document_title"]} (pages {c["page_start"]}-{c["page_end"]})')