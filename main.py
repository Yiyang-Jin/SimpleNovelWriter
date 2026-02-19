"""FastAPI 主入口。"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
from pathlib import Path

import storage
import settings_store
import qwen_client
import config

app = FastAPI(title="Qwen 双模型小说生成")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 静态文件
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ----- 请求体 -----
class CreateProjectReq(BaseModel):
    name: str
    world_setting: str = ""
    background_setting: str = ""
    character_setting: str = ""
    outline: str = ""


class UpdateProjectReq(BaseModel):
    name: Optional[str] = None
    world_setting: Optional[str] = None
    background_setting: Optional[str] = None
    character_setting: Optional[str] = None
    outline: Optional[str] = None


class GenerateChapterReq(BaseModel):
    project_id: str
    volume_idx: int
    chapter_idx: int
    user_direction: str


class AddVersionReq(BaseModel):
    project_id: str
    chapter_id: str
    content: str
    note: str = ""


class UpdateChapterReq(BaseModel):
    content: str


# ----- 路由 -----
@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")


@app.get("/api/projects")
def list_projects_api():
    return storage.list_projects()


@app.post("/api/projects")
def create_project_api(req: CreateProjectReq):
    pid = storage.create_project(
        name=req.name,
        world_setting=req.world_setting,
        background_setting=req.background_setting,
        character_setting=req.character_setting,
        outline=req.outline,
    )
    return {"project_id": pid, "message": "ok"}


@app.post("/api/projects/from-txt")
async def create_project_from_txt(
    name: str = Form(...),
    world_setting_file: Optional[UploadFile] = File(None),
    background_setting_file: Optional[UploadFile] = File(None),
    character_setting_file: Optional[UploadFile] = File(None),
    outline_file: Optional[UploadFile] = File(None),
):
    def _read(f) -> str:
        if not f or not f.filename:
            return ""
        return (f.file.read().decode("utf-8", errors="ignore")).strip()

    ws = await _read(world_setting_file) if world_setting_file else ""
    bs = await _read(background_setting_file) if background_setting_file else ""
    cs = await _read(character_setting_file) if character_setting_file else ""
    ol = await _read(outline_file) if outline_file else ""

    pid = storage.create_project(name=name, world_setting=ws, background_setting=bs, character_setting=cs, outline=ol)
    return {"project_id": pid, "message": "ok"}


@app.get("/api/projects/{project_id}")
def get_project_api(project_id: str):
    p = storage.get_project(project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    return p


@app.put("/api/projects/{project_id}")
def update_project_api(project_id: str, req: UpdateProjectReq):
    d = {k: v for k, v in req.model_dump().items() if v is not None}
    if not d:
        return {"message": "ok"}
    if not storage.get_project(project_id):
        raise HTTPException(404, "项目不存在")
    storage.update_project(project_id, **d)
    return {"message": "ok"}


@app.post("/api/projects/{project_id}/from-txt")
async def update_project_from_txt(
    project_id: str,
    world_setting_file: Optional[UploadFile] = File(None),
    background_setting_file: Optional[UploadFile] = File(None),
    character_setting_file: Optional[UploadFile] = File(None),
    outline_file: Optional[UploadFile] = File(None),
):
    p = storage.get_project(project_id)
    if not p:
        raise HTTPException(404, "项目不存在")

    def _read(f) -> str | None:
        if not f or not f.filename:
            return None
        return (f.file.read().decode("utf-8", errors="ignore")).strip()

    d = {}
    if (ws := await _read(world_setting_file)) is not None:
        d["world_setting"] = ws
    if (bs := await _read(background_setting_file)) is not None:
        d["background_setting"] = bs
    if (cs := await _read(character_setting_file)) is not None:
        d["character_setting"] = cs
    if (ol := await _read(outline_file)) is not None:
        d["outline"] = ol

    if d:
        storage.update_project(project_id, **d)
    return {"message": "ok"}


@app.get("/api/settings")
def get_settings_api():
    return settings_store.get_settings()


class UpdateSettingsReq(BaseModel):
    temperature: Optional[float] = None
    top_p: Optional[float] = None


@app.put("/api/settings")
def update_settings_api(req: UpdateSettingsReq):
    d = {k: v for k, v in req.model_dump().items() if v is not None}
    return settings_store.save_settings(d)


@app.post("/api/generate-chapter")
def generate_chapter_api(req: GenerateChapterReq):
    """生成新章节：1.规划走向 2.生成正文 3.章摘要 4.视情况压缩早期卷"""
    try:
        gen = settings_store.get_settings()
        rag = storage.get_rag_context(req.project_id, current_volume_idx=req.volume_idx)
        direction = qwen_client.generate_chapter_direction(
            rag_context=rag,
            user_direction=req.user_direction,
            volume_idx=req.volume_idx,
            chapter_idx=req.chapter_idx,
            temperature=gen.get("temperature"),
            top_p=gen.get("top_p"),
        )
        content = qwen_client.generate_chapter_content(
            rag_context=rag,
            direction=direction,
            volume_idx=req.volume_idx,
            chapter_idx=req.chapter_idx,
            temperature=gen.get("temperature"),
            top_p=gen.get("top_p"),
        )
        summary = qwen_client.summarize_chapter(
            content, direction,
            temperature=gen.get("temperature"),
            top_p=gen.get("top_p"),
        )

        chapter_id = storage.add_chapter(
            project_id=req.project_id,
            volume_idx=req.volume_idx,
            chapter_idx=req.chapter_idx,
            direction=direction,
            content=content,
            summary=summary,
        )

        # 早期卷：若该卷章节数达到阈值，压缩成卷摘要
        meta = storage.get_project(req.project_id)
        vols = meta.get("volumes", [])
        if req.volume_idx < len(vols):
            vol = vols[req.volume_idx]
            ch_ids = vol.get("chapters", [])
            if len(ch_ids) >= 3:  # 每卷≥3章时生成卷摘要
                ch_summaries = [
                    next((c["summary"] for c in meta.get("chapters", []) if c["id"] == cid), "")
                    for cid in ch_ids
                ]
                vol_sum = qwen_client.summarize_volume(
                    ch_summaries,
                    temperature=gen.get("temperature"),
                    top_p=gen.get("top_p"),
                )
                storage.update_volume_summary(req.project_id, req.volume_idx, vol_sum)

        return {"chapter_id": chapter_id, "direction": direction, "content": content, "summary": summary}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@app.get("/api/projects/{project_id}/chapters/{chapter_id}")
def get_chapter_api(project_id: str, chapter_id: str):
    content = storage.get_chapter_content(project_id, chapter_id)
    meta = storage.get_project(project_id)
    if not meta:
        raise HTTPException(404, "项目不存在")
    ch_info = next((c for c in meta.get("chapters", []) if c["id"] == chapter_id), None)
    if not ch_info:
        raise HTTPException(404, "章节不存在")
    return {"content": content, "direction": ch_info.get("direction"), "summary": ch_info.get("summary"), "versions": ch_info.get("versions", [])}


@app.put("/api/projects/{project_id}/chapters/{chapter_id}")
def update_chapter_api(project_id: str, chapter_id: str, req: UpdateChapterReq):
    storage.set_chapter_content(project_id, chapter_id, req.content)
    return {"message": "ok"}


@app.post("/api/versions")
def add_version_api(req: AddVersionReq):
    vid = storage.add_version(req.project_id, req.chapter_id, req.content, req.note)
    return {"version_id": vid, "message": "ok"}


@app.get("/api/projects/{project_id}/chapters/{chapter_id}/versions/{version_id}")
def get_version_api(project_id: str, chapter_id: str, version_id: str):
    content = storage.get_version_content(project_id, chapter_id, version_id)
    return {"content": content}


@app.post("/api/projects/{project_id}/chapters/{chapter_id}/summarize")
def summarize_chapter_api(project_id: str, chapter_id: str):
    """对已有章节重新做摘要（手动触发）。"""
    gen = settings_store.get_settings()
    content = storage.get_chapter_content(project_id, chapter_id)
    meta = storage.get_project(project_id)
    if not meta:
        raise HTTPException(404, "项目不存在")
    ch = next((c for c in meta.get("chapters", []) if c["id"] == chapter_id), None)
    if not ch:
        raise HTTPException(404, "章节不存在")
    direction = ch.get("direction", "")
    summary = qwen_client.summarize_chapter(
        content, direction,
        temperature=gen.get("temperature"),
        top_p=gen.get("top_p"),
    )
    storage.update_chapter_summary(project_id, chapter_id, summary)
    return {"summary": summary}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=29147)
