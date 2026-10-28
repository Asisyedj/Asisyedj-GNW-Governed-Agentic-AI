"""
Amazon Bedrock Client for Foundation Model Invocation
=====================================================
Provides integration with AWS Bedrock Foundation Models (Claude, Titan, Llama, Nova)
using AWS credentials and on-demand model subscriptions.
"""

import json
import os
import subprocess
from typing import Dict, Any, Optional

class BedrockModelClient:
    """Invokes AWS Bedrock Foundation Models via AWS CLI or boto3."""

    def __init__(self, region_name: str = "ap-southeast-2"):
        self.region_name = region_name

    def invoke_model(
        self,
        model_id: str = "amazon.nova-micro-v1:0",
        prompt: str = "Hello, summarize the current system status.",
        max_tokens: int = 1024
    ) -> Dict[str, Any]:
        """Invokes a foundation model in Amazon Bedrock."""
        # Check if boto3 is installed, else use aws cli fallback
        try:
            import boto3
            client = boto3.client("bedrock-runtime", region_name=self.region_name)

            if "anthropic" in model_id:
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}]
                })
            elif "amazon.nova" in model_id:
                body = json.dumps({
                    "messages": [{"role": "user", "content": [{"text": prompt}]}],
                    "inferenceConfig": {"max_new_tokens": max_tokens}
                })
            elif "amazon.titan" in model_id:
                body = json.dumps({
                    "inputText": prompt,
                    "textGenerationConfig": {"maxTokenCount": max_tokens}
                })
            else:
                body = json.dumps({"prompt": prompt, "max_tokens": max_tokens})

            response = client.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=body
            )
            raw = response["body"].read().decode("utf-8")
            parsed = json.loads(raw)
            return {"success": True, "model_id": model_id, "output": parsed}
        except ImportError:
            # Fallback to AWS CLI execution
            request_body = json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"max_new_tokens": max_tokens}
            })
            outfile = "bedrock_response_tmp.json"
            cmd = [
                "aws", "bedrock-runtime", "invoke-model",
                "--model-id", model_id,
                "--region", self.region_name,
                "--content-type", "application/json",
                "--accept", "application/json",
                "--body", request_body,
                outfile
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(outfile):
                with open(outfile, "r", encoding="utf-8") as f:
                    data = json.load(f)
                try:
                    os.remove(outfile)
                except OSError:
                    pass
                return {"success": True, "model_id": model_id, "output": data}
            return {
                "success": False,
                "model_id": model_id,
                "error": res.stderr or "AWS CLI execution failed"
            }
        except Exception as exc:
            return {"success": False, "model_id": model_id, "error": str(exc)}
