# Qwen 双模型小说生成

基于阿里云 Qwen 双模型的 Web 小说创作界面：逻辑模型（thinking）负责章节规划与摘要，Plus 模型负责正文生成；支持多级摘要、本地 JSON 存储、版本管理与 RAG 检索。

## 功能

- **双模型协作**
  - **qwen-max + thinking**：根据世界/背景/人物设定、大纲、已有摘要和用户指定剧情走向，输出本章具体走向
  - **qwen-plus**：根据本章走向生成格式化小说正文
  - **qwen-max + thinking**：对章节正文做摘要；早期卷将章摘要压缩为卷摘要

- **输入方式**：所有设定支持直接输入或 TXT 文件上传
- **存储**：本地 JSON + 文本文件
- **版本管理**：每章可保存多版本，支持查看历史
- **章节列表**：按卷/章浏览和管理

## 环境要求

- Python 3.10+
- **只需一个 API Key**：阿里云百炼 DashScope API Key（qwen-max、qwen-plus 共用）

## 本机使用

```powershell
# 1. 进入项目目录
cd d:\novel

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置 API Key（二选一）
# 方式 A：环境变量（推荐）
$env:DASHSCOPE_API_KEY="sk-你的key"

# 方式 B：在 config.py 中设置 DASHSCOPE_API_KEY = "sk-xxx"

# 4. 启动
python main.py
```

浏览器访问：**http://localhost:29147**

## RAG 读取逻辑

当前要生成的章节位于**第 n 卷**时：

| 卷 | 读取内容 |
|----|----------|
| 第 0 ~ n-2 卷 | 只读**卷摘要** |
| 第 n-1 卷 | 读该卷**所有章摘要** |
| 第 n 卷（当前卷） | 读该卷**已有的所有章摘要** |

示例：n=3 时，第 1 卷只读卷摘要；第 2 卷读全部章摘要；第 3 卷读本卷已写章节的章摘要。

## 项目结构

```
d:\novel\
  config.py      # API Key 与模型配置
  main.py        # FastAPI 入口
  qwen_client.py # Qwen API 调用（规划、正文、摘要）
  storage.py     # 本地 JSON + 文本存储
  static/        # Web UI
  data/          # 项目数据（自动创建）
```
