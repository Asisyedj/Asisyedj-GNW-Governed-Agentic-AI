import sys
import subprocess

result = subprocess.run([
    sys.executable, '-c', 
    "print('hello'); import sys; print('sys ok')"
], capture_output=True, text=True, timeout=10, cwd='D:\\GNW\\perplexity-browser-api')

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")