"""Qwen API 客户端：规划模型(thinking) + 正文模型(plus)。"""
import json
from typing import Optional

import dashscope
from dashscope import Generation
from dashscope.api_entities.dashscope_response import GenerationResponse

import config


def _call(
    model: str,
    messages: list[dict],
    enable_thinking: bool = False,
    thinking_budget: int = 8000,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> str:
    """调用千问 API。enable_thinking 时必须用流式，且只返回最终 content。"""
    dashscope.api_key = config.DASHSCOPE_API_KEY
    if not dashscope.api_key:
        raise ValueError("请设置环境变量 DASHSCOPE_API_KEY 或在 config.py 中配置")

    kwargs = {"model": model, "messages": messages}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature
    if top_p is not None:
        kwargs["top_p"] = top_p
    if enable_thinking:
        kwargs["result_format"] = "message"
        kwargs["enable_thinking"] = True
        kwargs["thinking_budget"] = thinking_budget
        kwargs["stream"] = True
        kwargs["incremental_output"] = True

    if enable_thinking:
        # 流式：只收集 content，忽略 reasoning_content
        completion = Generation.call(**kwargs)
        answer_content = ""
        for chunk in completion:
            if chunk.output and chunk.output.choices:
                msg = chunk.output.choices[0].message
                if msg and msg.content:
                    answer_content += msg.content or ""
        return answer_content.strip()

    resp: GenerationResponse = Generation.call(**kwargs)
    if resp.status_code != 200:
        raise RuntimeError(f"API 错误: {resp.code} {resp.message}")

    output = resp.output
    if not output or not output.choices:
        raise RuntimeError("API 返回空")

    text = output.choices[0].message.content or ""
    return text.strip()


def generate_chapter_direction(
    rag_context: str,
    user_direction: str,
    volume_idx: int,
    chapter_idx: int,
    temperature: float | None = None,
    top_p: float | None = None,
) -> str:
    """
    使用 qwen-max + thinking 生成本章具体走向。
    输入：RAG 上下文 + 用户指定剧情走向。
    输出：本章具体走向（纯文本）。
    """
    system = """你是一名专业的小说策划。根据世界设定、背景设定、人物设定、已有大纲和已写内容的摘要，以及用户指定的剧情走向，输出【本章的具体走向】。

输出要求：
- 只输出本章的具体剧情走向，不要写正文
- 简洁清晰，具体可执行：可包含关键场景、主要人物行动、情绪转折、伏笔埋设等
- 避免空洞概括，要能直接指导后续扩写
- 注意与前后章的衔接，保持剧情连贯
- 符合人物设定与世界观，不出现设定矛盾"""

    user = f"""{rag_context}

---
【用户指定的剧情走向】
{user_direction}

---
请输出：第{volume_idx + 1}卷 第{chapter_idx + 1}章 的具体走向。只输出走向内容，不要其他说明。"""

    return _call(
        model=config.MODEL_PLANNING,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        enable_thinking=config.MODEL_PLANNING_THINKING,
        temperature=temperature,
        top_p=top_p,
    )


def generate_chapter_content(
    rag_context: str,
    direction: str,
    volume_idx: int,
    chapter_idx: int,
    temperature: float | None = None,
    top_p: float | None = None,
) -> str:
    """
    使用 qwen-plus 根据本章走向生成格式化小说正文。
    篇幅要求：config.CHAPTER_MIN_CHARS ~ CHAPTER_MAX_CHARS 字。
    """
    min_c, max_c = config.CHAPTER_MIN_CHARS, config.CHAPTER_MAX_CHARS
    system = f"""你是一名专业的小说作家。根据设定、大纲、已有内容摘要和本章具体走向，写出本章的完整小说正文。

输出要求：
- 纯正文，不要标题、不要章节号
- 篇幅严格控制在 {min_c} 字以上、{max_c} 字以内（含标点）
- 采用日本轻小说中文译本的常见翻译风格：简洁、口语化、节奏明快，对话自然
- 多分段，单段不宜过长：避免大段连贯叙述，适当换行，每段以 1–3 句为宜，对话可单独成段
- 与设定和前后文风格一致，人物性格、口吻符合人物设定"""

    user = f"""{rag_context}

---
【本章具体走向】
{direction}

---
请写出第{volume_idx + 1}卷 第{chapter_idx + 1}章的完整正文。篇幅须在 {min_c}–{max_c} 字之间。只输出正文内容。"""

    return _call(
        model=config.MODEL_CONTENT,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        enable_thinking=False,
        max_tokens=config.CHAPTER_MAX_TOKENS,
        temperature=temperature,
        top_p=top_p,
    )


def summarize_chapter(content: str, direction: str, temperature: float | None = None, top_p: float | None = None) -> str:
    """
    使用 qwen-max + thinking 对章节正文做摘要。
    只对章节摘要，输出简洁的摘要文本。
    """
    system = """你是摘要专家。将给定的小说章节正文压缩成一段简洁的摘要，用于后续 RAG 检索和保持剧情连贯。

要求：
- 篇幅 100–300 字
- 按时间或因果顺序概括，保留关键情节、人物行为、重要对话或决断
- 包含人物关系变化、场景转换、情绪转折等对后续剧情有影响的信息
- 只输出摘要正文，不要加标题或说明"""

    user = f"""【本章走向参考】
{direction[:500]}

【正文】
{content[:8000]}

---
请输出本章摘要（100-300字）。只输出摘要内容。"""

    return _call(
        model=config.MODEL_PLANNING,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        enable_thinking=config.MODEL_PLANNING_THINKING,
        thinking_budget=4000,
        temperature=temperature,
        top_p=top_p,
    )


def summarize_volume(chapter_summaries: list[str], temperature: float | None = None, top_p: float | None = None) -> str:
    """
    使用 qwen-max + thinking 将多章摘要压缩成卷摘要。
    对过于早期的卷，把章摘要压成卷摘要。
    """
    if not chapter_summaries:
        return ""
    system = """你是摘要专家。将多章摘要压缩成该卷的一段卷摘要，用于 RAG 检索。

要求：
- 篇幅 200–500 字
- 突出本卷主线与重要支线，保留核心情节线、人物弧光、重要转折点
- 概括人物关系变化、主要冲突与解决、伏笔收放（如有）
- 若与前/后卷有承启关系，可简要提及
- 只输出摘要正文，不要加标题或说明"""

    combined = "\n\n".join(f"第{i+1}章：{s}" for i, s in enumerate(chapter_summaries))
    user = f"""【各章摘要】
{combined[:6000]}

---
请输出该卷的卷摘要（200-500字）。只输出摘要内容。"""

    return _call(
        model=config.MODEL_PLANNING,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        enable_thinking=config.MODEL_PLANNING_THINKING,
        thinking_budget=4000,
        temperature=temperature,
        top_p=top_p,
    )
