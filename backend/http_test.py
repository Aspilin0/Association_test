"""HTTP 冒烟测试：走真实 aiohttp 服务，结果写入 UTF-8 文件供读取。"""
import json
import time

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> None:
    # 等待服务就绪
    for _ in range(30):
        try:
            httpx.get(BASE + "/health", timeout=2)
            break
        except Exception:
            time.sleep(0.5)
    else:
        print("server not up")
        return

    out = []

    r = httpx.get(BASE + "/health")
    out.append(["health", r.status_code, r.json()])

    r = httpx.post(BASE + "/api/v1/sessions", json={"seed_words": ["家", "母亲"]})
    data = r.json()
    out.append(["create", r.status_code, data])
    sid = data["session"]["id"]

    for w, rt in [("房子", 1350), ("童年", 2100), ("拥抱", 900)]:
        r = httpx.post(
            BASE + f"/api/v1/sessions/{sid}/submit",
            json={"word": w, "reaction_time_ms": rt, "source": "selected"},
        )
        out.append([f"submit_{w}", r.status_code, r.json()])

    r = httpx.get(BASE + f"/api/v1/sessions/{sid}/network")
    out.append(["network", r.status_code, r.json()])

    r = httpx.post(BASE + "/api/v1/sessions/does-not-exist/submit",
                   json={"word": "x", "reaction_time_ms": 1, "source": "selected"})
    out.append(["not_found", r.status_code, r.json()])

    with open("http_result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("wrote http_result.json")


if __name__ == "__main__":
    main()
