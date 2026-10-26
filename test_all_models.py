from dotenv import load_dotenv
import os, urllib.request, json

load_dotenv(r'D:\GNW\perplexity-browser-api\.env')
token = os.getenv('PERPLEXITY_SESSION_TOKEN')

models_to_test = [
    'anthropic/claude-sonnet-5.5',
    'openai/gpt5',
    'google/gemini-3.8-flash',
    'x-ai/grok-4.7',
    'perplexity/best',
]

print("Testing 5 models via GNW Perplexity Bridge:\n")
for model in models_to_test:
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': 'Reply with just: OK'}],
        'max_tokens': 20,
        'stream': False
    }
    req = urllib.request.Request(
        'http://127.0.0.1:8000/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.loads(res.read().decode())
            content = data['choices'][0]['message']['content'][:30]
            print(f"[PASS] {model}: {content}")
    except Exception as e:
        print(f"[FAIL] {model}: {str(e)[:80]}")

print("\nAll tests complete!")
