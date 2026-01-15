import os, json, sys
import yaml
import requests

NETWORK = os.environ.get("SCRIPTWORLD_HOST", "http://127.0.0.1:8700")
SCENARIO_DIR = os.path.expanduser("~/script_world/scenarios")

# 你网络里需要有一个“HTTP 身份”，用来发事件
SENDER_ID = "admin"          # 也可以用 ScriptWorldLobby
CHANNEL = "general"

def post_event(payload: dict):
    r = requests.post(f"{NETWORK}/api/send_event", json=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"send_event failed: {r.status_code} {r.text}")

def send_channel(text: str):
    post_event({
        "event": {
            "type": "thread.channel_message",
            "source": SENDER_ID,
            "target": f"channel:{CHANNEL}",
            "content": {"text": text},
        }
    })

def send_dm(target_id: str, text: str):
    post_event({
        "event": {
            "type": "thread.direct_message",
            "source": SENDER_ID,
            "target": f"agent:{target_id}",
            "content": {"text": text},
        }
    })

def main():
    if len(sys.argv) < 2:
        print("Usage: python load_scenario_and_boot.py <scenario_id>")
        sys.exit(1)

    scenario_id = sys.argv[1]
    path = os.path.join(SCENARIO_DIR, f"{scenario_id}.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Scenario not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        scenario = yaml.safe_load(f)

    title = scenario.get("title", scenario_id)

    # 这里假设你的 scenario.yaml 里 roles 结构类似你设计的：
    roles = scenario.get("roles", [])

    # 先在频道发开场（MVP）
    send_channel(f"🎭【DM】已加载剧本：《{title}》。即将开始分配角色与第一幕。")

    # 给 DM 私聊发送“剧本已加载”
    send_dm("universal_dm", "【SCENARIO_LOADED】\n" + json.dumps({
        "scenario_id": scenario_id,
        "title": title,
        "channel": CHANNEL
    }, ensure_ascii=False, indent=2))

    # 给 NPC 发 ROLE PACK（MVP：只发 public/hidden + identity）
    for r in roles:
        if r.get("type") != "ai":
            continue
        rid = r.get("id")
        # 你需要保证 ai 角色 id 和 agent_id 对得上
        # 例：role id = npc_1 -> agent_id = npc_1
        agent_id = rid

        pack = {
            "role_id": rid,
            "display": r.get("display"),
            "identity": r.get("identity"),
            "public_info": r.get("public_info", []),
            "hidden_info": r.get("hidden_info", []),
        }
        send_dm(agent_id, "【ROLE PACK】\n" + json.dumps(pack, ensure_ascii=False, indent=2))

    send_channel("✅ 角色设定包已下发给 NPC。玩家请在频道回复：我准备好了（或直接提问开始）。")

if __name__ == "__main__":
    main()
