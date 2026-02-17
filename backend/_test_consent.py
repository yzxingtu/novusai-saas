"""Quick script to check and update consent_mode for agent skill bindings"""
import httpx

BASE = "http://localhost:5320/api"

# Login
r = httpx.post(f"{BASE}/admin/auth/login", json={"username": "admin", "password": "admin123456"})
token = r.json()["data"]["token"]
headers = {"Authorization": f"Bearer {token}"}

# Get agent 20 skill bindings
r2 = httpx.get(f"{BASE}/admin/ai/agents/20/skills", headers=headers)
print("=== Agent 20 Skill Bindings ===")
print(f"Status: {r2.status_code}")
if r2.status_code == 200:
    bindings = r2.json().get("data", [])
    for b in bindings:
        print(f"  id={b.get('id')} package={b.get('package_name')} consent_mode={b.get('consent_mode')} enabled={b.get('enabled')}")
else:
    print(r2.text[:500])

# Also check agent 28 (测试助手) and 15 (智能助手)
for aid in [28, 15]:
    r3 = httpx.get(f"{BASE}/admin/ai/agents/{aid}/skills", headers=headers)
    print(f"\n=== Agent {aid} Skill Bindings ===")
    print(f"Status: {r3.status_code}")
    if r3.status_code == 200:
        bindings = r3.json().get("data", [])
        for b in bindings:
            print(f"  id={b.get('id')} package={b.get('package_name')} consent_mode={b.get('consent_mode')} enabled={b.get('enabled')}")
    else:
        print(r3.text[:300])
