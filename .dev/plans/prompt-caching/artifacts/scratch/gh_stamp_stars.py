from pathlib import Path
import httpx

repos = [
    "Belkins/ai-dive-deep",
    "abundantbeing/hermes-browser-extension",
    "HKUDS/LightRAG",
    "StructuPath/herdr-browser",
    "antonyrag/ragleap-core",
    "hanyeol/model-compose",
    "MikkoParkkola/mcp-gateway",
    "Mnemosyne-OS/Mnemosyne-Neural-OS",
]
token = None
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("GITHUB_TOKEN="):
        token = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {token}",
}
with httpx.Client(timeout=30) as client:
    for repo in repos:
        r = client.get(f"https://api.github.com/repos/{repo}", headers=headers)
        if r.status_code != 200:
            print(f"{r.status_code}\t?\t{repo}")
            continue
        d = r.json()
        print(f"{d.get('stargazers_count')}\t{d.get('language')}\t{repo}")
