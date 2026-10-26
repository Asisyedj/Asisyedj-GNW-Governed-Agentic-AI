import sys
import subprocess

# Run pytest on the test file
result = subprocess.run([
    sys.executable, '-m', 'pytest', 
    'personal_agent/tests/test_state_persistence.py', 
    '-v', '--tb=short'
], capture_output=True, text=True, timeout=120, cwd='D:\\GNW\\perplexity-browser-api')

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")