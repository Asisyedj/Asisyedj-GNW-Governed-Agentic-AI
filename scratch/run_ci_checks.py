import subprocess
import os

repo_path = r"d:\GNW\perplexity-browser-api"
os.chdir(repo_path)

logs_dir = os.path.join(repo_path, "ci_logs")
os.makedirs(logs_dir, exist_ok=True)

test_log = os.path.join(logs_dir, "pytest_run.log")
security_log = os.path.join(logs_dir, "bandit_run.log")

print("Running pytest via uv...")
with open(test_log, "w", encoding="utf-8") as f:
    res_test = subprocess.run(["uv", "run", "--with", "pytest", "pytest"], stdout=f, stderr=subprocess.STDOUT, text=True)

print(f"Pytest exit code: {res_test.returncode}")

print("Running bandit via uv...")
with open(security_log, "w", encoding="utf-8") as f:
    res_bandit = subprocess.run(["uv", "run", "--with", "bandit", "bandit", "-r", "."], stdout=f, stderr=subprocess.STDOUT, text=True)

print(f"Bandit exit code: {res_bandit.returncode}")
print("CI checks completed successfully.")
