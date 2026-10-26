import sys
import subprocess

result = subprocess.run([
    sys.executable, '-c', 
    "import sys; sys.path.insert(0, 'D:\\\\GNW\\\\perplexity-browser-api'); print('path ok'); from personal_agent.bridge.supervisor import BridgeSupervisor; print('supervisor ok')"
], capture_output=True, text=True, timeout=30, cwd='D:\\GNW\\perplexity-browser-api')

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")