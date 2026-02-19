"""本地 JSON + 文本存储。"""
import json
import os
import uuid
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

import config

# 确保目录存在
Path(config.PROJECTS_DIR).mkdir(parents=True, exist_ok=True)


def _project_path(project_id: str) -> Path:
    return Path(config.PROJECTS_DIR) / project_id


def _ensure_project(project_id: str) -> Path:
    p = _project_path(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_projects() -> list[dict]:
    """列出所有项目。"""
    base = Path(config.PROJECTS_DIR)
    if not base.exists():
        return []
    out = []
    for d in base.iterdir():
        if d.is_dir():
            meta_path = d / "meta.json"
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    out.append({"id": d.name, **meta})
                except Exception:
                    pass
    return out


def create_project(name: str, world_setting: str = "", background_setting: str = "", character_setting: str = "", outline: str = "") -> str:
    """创建新项目，返回 project_id。"""
    project_id = str(uuid.uuid4())[:8]
    base = _ensure_project(project_id)
    meta = {
        "name": name,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "world_setting": world_setting,
        "background_setting": background_setting,
        "character_setting": character_setting,
        "outline": outline,
        "volumes": [],
        "chapters": [],
    }
    with open(base / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return project_id


def get_project(project_id: str) -> Optional[dict]:
    """获取项目元信息。"""
    base = _project_path(project_id)
    meta_path = base / "meta.json"
    if not meta_path.exists():
        return None
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_project(project_id: str, **kwargs) -> bool:
    """更新项目字段。"""
    meta = get_project(project_id)
    if not meta:
        return False
    meta.update(kwargs)
    meta["updated_at"] = datetime.now().isoformat()
    base = _project_path(project_id)
    with open(base / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return True


def add_chapter(project_id: str, volume_idx: int, chapter_idx: int, direction: str, content: str = "", summary: str = "") -> str:
    """添加章节，返回 chapter_id。"""
    base = _ensure_project(project_id)
    chapter_id = str(uuid.uuid4())[:8]
    meta = get_project(project_id)
    if not meta:
        raise ValueError("项目不存在")

    chapter_info = {
        "id": chapter_id,
        "volume_idx": volume_idx,
        "chapter_idx": chapter_idx,
        "direction": direction,
        "summary": summary,
        "created_at": datetime.now().isoformat(),
        "versions": [],
    }

    # 确保 volumes 结构
    while len(meta.get("volumes", [])) <= volume_idx:
        meta["volumes"].append({"chapters": [], "summary": ""})
    meta["volumes"][volume_idx]["chapters"].append(chapter_id)

    if "chapters" not in meta:
        meta["chapters"] = []
    meta["chapters"].append(chapter_info)
    meta["updated_at"] = datetime.now().isoformat()

    # 写入章节内容
    (base / "chapters").mkdir(exist_ok=True)
    content_path = base / "chapters" / f"{chapter_id}.txt"
    with open(content_path, "w", encoding="utf-8") as f:
        f.write(content)

    # 先保存 meta，再添加版本（add_version 会读取 meta）
    with open(base / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    add_version(project_id, chapter_id, content, "初始生成")

    return chapter_id


def add_version(project_id: str, chapter_id: str, content: str, note: str = "") -> str:
    """为章节添加版本。"""
    base = _project_path(project_id)
    version_id = str(uuid.uuid4())[:8]
    versions_dir = base / "versions"
    versions_dir.mkdir(exist_ok=True)
    v_path = versions_dir / f"{chapter_id}_{version_id}.txt"
    with open(v_path, "w", encoding="utf-8") as f:
        f.write(content)

    meta = get_project(project_id)
    if not meta:
        return version_id
    for ch in meta.get("chapters", []):
        if ch["id"] == chapter_id:
            ch.setdefault("versions", [])
            ch["versions"].append({
                "id": version_id,
                "note": note,
                "created_at": datetime.now().isoformat(),
            })
            break
    update_project(project_id, **meta)
    return version_id


def get_chapter_content(project_id: str, chapter_id: str) -> str:
    """获取章节当前内容。"""
    base = _project_path(project_id)
    p = base / "chapters" / f"{chapter_id}.txt"
    if not p.exists():
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def set_chapter_content(project_id: str, chapter_id: str, content: str) -> None:
    """设置章节当前内容。"""
    base = _project_path(project_id)
    (base / "chapters").mkdir(exist_ok=True)
    with open(base / "chapters" / f"{chapter_id}.txt", "w", encoding="utf-8") as f:
        f.write(content)


def get_version_content(project_id: str, chapter_id: str, version_id: str) -> str:
    """获取指定版本内容。"""
    base = _project_path(project_id)
    p = base / "versions" / f"{chapter_id}_{version_id}.txt"
    if not p.exists():
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def update_chapter_summary(project_id: str, chapter_id: str, summary: str) -> None:
    """更新章节摘要。"""
    meta = get_project(project_id)
    if not meta:
        return
    for ch in meta.get("chapters", []):
        if ch["id"] == chapter_id:
            ch["summary"] = summary
            break
    meta["updated_at"] = datetime.now().isoformat()
    base = _project_path(project_id)
    with open(base / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def update_volume_summary(project_id: str, volume_idx: int, summary: str) -> None:
    """更新卷摘要。"""
    meta = get_project(project_id)
    if not meta:
        return
    vols = meta.get("volumes", [])
    while len(vols) <= volume_idx:
        vols.append({"chapters": [], "summary": ""})
    vols[volume_idx]["summary"] = summary
    meta["volumes"] = vols
    meta["updated_at"] = datetime.now().isoformat()
    base = _project_path(project_id)
    with open(base / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def get_rag_context(project_id: str, current_volume_idx: int) -> str:
    """
    构建 RAG 上下文，读取逻辑（当前卷为 n = current_volume_idx）：
    - 卷 0 ~ n-2：只读卷摘要
    - 卷 n-1：读该卷所有章摘要
    - 卷 n（当前卷）：读该卷已有的所有章摘要
    """
    meta = get_project(project_id)
    if not meta:
        return ""

    parts = []
    if meta.get("world_setting"):
        parts.append("【世界设定】\n" + meta["world_setting"])
    if meta.get("background_setting"):
        parts.append("【背景设定】\n" + meta["background_setting"])
    if meta.get("character_setting"):
        parts.append("【人物设定】\n" + meta["character_setting"])
    if meta.get("outline"):
        parts.append("【整体大纲】\n" + meta["outline"])

    vols = meta.get("volumes", [])
    chapters = meta.get("chapters", [])

    # 卷 0 ~ n-2：只读卷摘要（vi = 0, 1, ..., n-2）
    for vi in range(max(0, current_volume_idx - 1)):
        if vi < len(vols) and vols[vi].get("summary"):
            parts.append(f"【第{vi + 1}卷摘要】\n{vols[vi]['summary']}")

    # 卷 n-1：读该卷所有章摘要
    if current_volume_idx >= 1 and current_volume_idx - 1 < len(vols):
        prev_ch_ids = vols[current_volume_idx - 1].get("chapters", [])
        for ch in chapters:
            if ch["id"] in prev_ch_ids:
                s = ch.get("summary") or ch.get("direction", "")
                if s:
                    parts.append(f"【第{current_volume_idx}卷 第{ch.get('chapter_idx', 0) + 1}章】\n{s}")

    # 卷 n（当前卷）：读该卷已有的所有章摘要
    if current_volume_idx < len(vols):
        curr_ch_ids = vols[current_volume_idx].get("chapters", [])
        for ch in chapters:
            if ch["id"] in curr_ch_ids:
                s = ch.get("summary") or ch.get("direction", "")
                if s:
                    parts.append(f"【第{current_volume_idx + 1}卷 第{ch.get('chapter_idx', 0) + 1}章】\n{s}")

    return "\n\n".join(parts)
