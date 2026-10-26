"""Write a JSON report to the `data/reports` folder.
The filename includes a timestamp and the target hostname.
"""
import json, datetime, pathlib, os

def save_report(target: str, results: list):
    ts = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    hostname = target.split('//')[1].split('/')[0].replace('.', '_')
    out_dir = pathlib.Path(__file__).parents[2] / 'data' / 'reports'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{hostname}_{ts}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'target': target, 'results': results}, f, indent=2)
    return str(out_path)
