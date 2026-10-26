import sys
import subprocess

result = subprocess.run([
    sys.executable, 'D:\\GNW\\perplexity-browser-api\\test_supervisor.py'
], capture_output=True, text=True, timeout=60, cwd='D:\\GNW\\perplexity-browser-api')

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")