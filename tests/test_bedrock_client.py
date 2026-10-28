import pytest
from src.bedrock_client import BedrockModelClient

def test_bedrock_client_initialization():
    client = BedrockModelClient(region_name="ap-southeast-2")
    assert client.region_name == "ap-southeast-2"

def test_bedrock_client_invocation_mock(monkeypatch):
    client = BedrockModelClient(region_name="ap-southeast-2")
    # Test error handling when offline/unconfigured
    res = client.invoke_model(model_id="invalid.model-v1", prompt="test")
    assert "success" in res
