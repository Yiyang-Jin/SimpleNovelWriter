"""配置：API Key 和模型 ID。"""
import os

# 阿里云 DashScope API Key（环境变量 DASHSCOPE_API_KEY 或在此设置）
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

# 模型配置（阿里云百炼 DashScope）
# 逻辑/规划 + 摘要：qwen-max（最强推理），启用 thinking
MODEL_PLANNING = "qwen-max"
MODEL_PLANNING_THINKING = True

# 正文生成：qwen-plus
MODEL_CONTENT = "qwen-plus"

# 正文篇幅（字）
CHAPTER_MIN_CHARS = 6000
CHAPTER_MAX_CHARS = 8000
# 正文生成 max_tokens（约 1.5 字/token，8k 字需 ~12000）
CHAPTER_MAX_TOKENS = 12000

# 存储路径
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
