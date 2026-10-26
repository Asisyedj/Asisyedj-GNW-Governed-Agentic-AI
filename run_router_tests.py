import sys
import subprocess

result = subprocess.run([
    sys.executable, '-m', 'pytest', 
    'test_router_integration.py', 
    '-v', '--tb=short'
], capture_output=True, text=True, timeout=120, cwd='D:\\GNW\\perplexity-browser-api')

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")