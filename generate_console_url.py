import json
import urllib.parse
import urllib.request
import subprocess
import sys
import os

def main():
    print("Generating AWS Console Direct Login URL with full session policy...")
    policy_path = os.path.abspath("session_policy.json")
    
    # Run aws sts get-federation-token with session policy
    cmd = [
        "aws", "sts", "get-federation-token",
        "--name", "AntigravvityAdminSession",
        "--policy", f"file://{policy_path}",
        "--duration-seconds", "43200",
        "--output", "json"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Error with 43200s, trying 3600s:", res.stderr)
        cmd[6] = "3600"
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("Failed to get federation token with policy:", res.stderr)
            sys.exit(1)

    data = json.loads(res.stdout)
    creds = data["Credentials"]
    session_json = json.dumps({
        "sessionId": creds["AccessKeyId"],
        "sessionKey": creds["SecretAccessKey"],
        "sessionToken": creds["SessionToken"]
    })

    # Step 2: Request sign-in token
    params = urllib.parse.urlencode({
        "Action": "getSigninToken",
        "Session": session_json
    })
    token_url = f"https://signin.aws.amazon.com/federation?{params}"
    req = urllib.request.Request(token_url)
    with urllib.request.urlopen(req) as response:
        resp_data = json.loads(response.read().decode("utf-8"))

    signin_token = resp_data["SigninToken"]

    # Step 3: Build final login URL to ECS Clusters in ap-southeast-2
    dest = "https://ap-southeast-2.console.aws.amazon.com/ecs/v2/clusters?region=ap-southeast-2"
    login_params = urllib.parse.urlencode({
        "Action": "login",
        "Issuer": "Antigravvity",
        "Destination": dest,
        "SigninToken": signin_token
    })
    console_url = f"https://signin.aws.amazon.com/federation?{login_params}"

    with open("aws_console_login_url.txt", "w", encoding="utf-8") as f:
        f.write(console_url)

    print("\nSUCCESS! Direct AWS Console Login URL generated with Full Session Policy:")
    print(console_url)

if __name__ == "__main__":
    main()
