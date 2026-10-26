import sys, os
# Ensure the repository root is on the import path
repo_root = r'D:\\GNW\\perplexity-browser-api'
sys.path.append(repo_root)

# Now import and execute the probe script's main function
from personal_agent.health.run_probes import main

if __name__ == '__main__':
    # optional: allow limit via env var or default
    limit = int(os.getenv('PROBE_LIMIT', '15'))
    main(limit)
