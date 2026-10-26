"""Verify GNW localhost bridge without printing credentials or model output."""
import json, urllib.request, urllib.error
from gnw_secrets import get_bridge_key
BASE="http://127.0.0.1:8000"
def call(path,payload=None,key=None,timeout=20):
    h={}
    if key is not None: h["Authorization"]="Bearer "+key
    data=json.dumps(payload).encode() if payload is not None else None
    if data is not None: h["Content-Type"]="application/json"
    req=urllib.request.Request(BASE+path,data=data,headers=h,method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return r.status,r.read()
    except urllib.error.HTTPError as e: return e.code,b""
def main():
    st,body=call("/health",timeout=5)
    health=json.loads(body.decode()) if st==200 else {}
    if st!=200 or health.get("status")!="ok": raise SystemExit("HEALTH_CHECK=FAIL")
    print("HEALTH_CHECK=PASS; status=200")
    st,_=call("/v1/models",key="invalid-local-key",timeout=5)
    if st!=401: raise SystemExit(f"UNAUTHORIZED_REQUEST=FAIL; status={st}")
    print("UNAUTHORIZED_REQUEST=PASS; status=401")
    key=get_bridge_key()
    st,body=call("/v1/models",key=key,timeout=15)
    models=json.loads(body.decode()) if st==200 else {}
    count=len(models.get("data",[]))
    if st!=200 or count<1: raise SystemExit(f"AUTHENTICATED_MODELS=FAIL; status={st}; count={count}")
    print(f"AUTHENTICATED_MODELS=PASS; status=200; count={count}")
    st,body=call("/v1/chat/completions",{"model":"perplexity/sonar-2","messages":[{"role":"user","content":"Reply with exactly GNW_BRIDGE_OK and no other text."}],"stream":False},key=key,timeout=90)
    data=json.loads(body.decode()) if st==200 else {}
    choices=data.get("choices",[])
    n=len(str(choices[0].get("message",{}).get("content",""))) if choices else 0
    if st!=200 or not choices or n==0: raise SystemExit(f"API_INVOCATION=FAIL; status={st}; choices={len(choices)}")
    print(f"API_INVOCATION=PASS; status=200; choices={len(choices)}; response_chars={n}")
if __name__=="__main__": main()
