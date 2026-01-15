#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from pathlib import Path
import string
import sys
import time
import json

import requests

try:
    import yaml  # pyyaml
except Exception:
    yaml = None


SCENARIOS_DIR = Path.home() / "script_world" / "scenarios"
VALID_SUFFIX = (".yaml", ".yml")

NETWORK_HTTP = "http://127.0.0.1:8700"
LOBBY_CHANNEL = "general"  # 你的 network.yaml 默认有 general


WELCOME = (
    "🕵️ 欢迎来到 ScriptWorld 探案馆！\n"
    "这里是【三人剧本·AI可补位】上车入口～\n"
    "请选择一个剧本（输入字母即可，比如 A）：\n"
)
INVALID = "😵 你的输入有点问题，请重新选择哇～（请输入 A/B/C…）"
CONFIRM = "✅ 你选择的是：{title}\n是否确定开启？请输入：是 / 否"
CONFIRM_INVALID = "😵 我没看懂，请输入：是 或 否"
SENDING = "📨 已为你把剧本自动发送到 lobby（general）频道，接下来去 Studio 跟 DM 继续：我扮演：<角色> → 开始游戏"


def list_yaml_files() -> list[Path]:
    if not SCENARIOS_DIR.exists():
        raise FileNotFoundError(f"找不到目录：{SCENARIOS_DIR}")
    files = []
    for p in sorted(SCENARIOS_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in VALID_SUFFIX:
            files.append(p)
    return files


def display_title(p: Path) -> str:
    # 文件名去掉后缀作为展示名：博物馆惊魂：失窃的汝窑盏.yaml -> 博物馆惊魂：失窃的汝窑盏
    return p.stem


def build_menu(files: list[Path]) -> tuple[str, dict[str, Path]]:
    letters = list(string.ascii_uppercase)
    mapping: dict[str, Path] = {}
    lines = [WELCOME]

    for i, f in enumerate(files):
        if i >= len(letters):
            break
        key = letters[i]
        mapping[key] = f
        lines.append(f"{key}. {display_title(f)}")

    if not mapping:
        lines.append("（当前 scenarios 目录下没有 *.yaml 剧本文件）")

    return "\n".join(lines), mapping


def validate_yaml_syntax(text: str) -> tuple[bool, str]:
    if yaml is None:
        return True, "（未安装 pyyaml，跳过 YAML 语法校验）"
    try:
        yaml.safe_load(text)
        return True, "YAML 语法校验通过"
    except Exception as e:
        return False, f"YAML 语法可能有问题：{e}"


def ask_choice(mapping: dict[str, Path]) -> Path:
    while True:
        c = input("\n你的选择：").strip().upper()
        if c in mapping:
            return mapping[c]
        print(INVALID)


def ask_confirm(title: str) -> bool:
    while True:
        ans = input("\n" + CONFIRM.format(title=title) + "\n你的输入：").strip()
        if ans in ("是", "Y", "y", "yes", "YES", "Yes"):
            return True
        if ans in ("否", "N", "n", "no", "NO", "No"):
            return False
        print(CONFIRM_INVALID)


def http_post(path: str, payload: dict) -> dict:
    url = NETWORK_HTTP + path
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


def ensure_http_agent(agent_id: str = "ScriptWorldLobby") -> None:
    """
    Studio 的网页用户会被当成一个 HTTP agent 注册（你日志里 QuickWorker0731 就是）。
    我们这里也注册一个，方便往频道发消息。
    """
    payload = {
        "agent_id": agent_id,
        "display_name": agent_id,
        # 某些版本会有 secret 字段；你的网络不要求密码，所以留空即可
        "secret": "",
        "channels": [LOBBY_CHANNEL],
        "metadata": {"platform": "cli"},
    }
    # 如果 /api/register 不存在也没关系，我们后面仍尝试 send_event
    try:
        http_post("/api/register", payload)
    except Exception:
        pass


def send_channel_message(text: str, sender_id: str = "ScriptWorldLobby") -> None:
    """
    发送一条“频道消息”。不同版本字段可能略有差异；
    你的日志显示网络内部确实在使用 /api/send_event，所以这里按常见格式发。
    """
    payload = {
        "event": {
            "type": "openagents.mods.workspace.messaging.send_channel_message",
            "source": sender_id,
            "target": "system:system",
            "data": {
                "channel": LOBBY_CHANNEL,
                "content": {"text": text},
            },
        }
    }

    # 兼容：有些版本是平铺字段而不是 event 包裹
    fallback_payload = {
        "type": "openagents.mods.workspace.messaging.send_channel_message",
        "source": sender_id,
        "target": "system:system",
        "channel": LOBBY_CHANNEL,
        "content": {"text": text},
    }

    try:
        http_post("/api/send_event", payload)
    except Exception:
        http_post("/api/send_event", fallback_payload)


def main() -> None:
    try:
        files = list_yaml_files()
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

    menu, mapping = build_menu(files)
    print(menu)
    if not mapping:
        sys.exit(0)

    selected = ask_choice(mapping)
    title = display_title(selected)

    if not ask_confirm(title):
        print("已取消。欢迎下次再来～")
        sys.exit(0)

    content = selected.read_text(encoding="utf-8")
    ok, msg = validate_yaml_syntax(content)
    print(("✅ " if ok else "⚠️ ") + msg)

    # 注册一个 CLI “HTTP agent”（可选，但更稳）
    ensure_http_agent("ScriptWorldLobby")

    # 先发“加载剧本”，再发 YAML
    send_channel_message("加载剧本", sender_id="ScriptWorldLobby")
    time.sleep(0.3)
    send_channel_message(f"```yaml\n{content.rstrip()}\n```", sender_id="ScriptWorldLobby")

    print("\n" + SENDING)


if __name__ == "__main__":
    main()
