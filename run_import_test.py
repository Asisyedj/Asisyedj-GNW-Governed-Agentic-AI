import sys
import subprocess

result = subprocess.run([
    sys.executable, '-c', 
    "import sys; sys.path.insert(0, 'D:\\\\GNW\\\\perplexity-browser-api'); print('path ok'); from personal_agent.state.persistence import get_state_store; print('persistence ok')"
], capture_output=True, text=True, timeout=30, cwd='D:\\GNW\\perplexity-browser-api')

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")