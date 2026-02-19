"""生成参数设置：temperature、top_p 等。存储于 data/settings.json。"""
import json
import os
from pathlib import Path

import config

SETTINGS_PATH = Path(config.DATA_DIR) / "settings.json"

DEFAULTS = {
    "temperature": 0.8,
    "top_p": 0.9,
}


def get_settings() -> dict:
    """获取当前设置，缺失则用默认值。"""
    if not SETTINGS_PATH.exists():
        return DEFAULTS.copy()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return DEFAULTS.copy()
    out = DEFAULTS.copy()
    for k in DEFAULTS:
        if k in data and data[k] is not None:
            out[k] = float(data[k])
    return out


def save_settings(updates: dict) -> dict:
    """保存设置，返回合并后的完整设置。"""
    Path(config.DATA_DIR).mkdir(parents=True, exist_ok=True)
    cur = get_settings()
    for k, v in updates.items():
        if k in DEFAULTS and v is not None:
            try:
                cur[k] = float(v)
            except (TypeError, ValueError):
                pass
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    return cur
