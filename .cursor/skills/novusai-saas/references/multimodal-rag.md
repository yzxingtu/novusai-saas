# 多模态 RAG 规范（M263）

> 当前知识库支持图片 / PDF 内嵌图片 / PPTX / 音频 / 视频进入统一解析管线；图片/PDF 图片走 Vision 描述，音频/视频已接入 parser factory 与处理编排，但若描述器未产出文本，文档会明确进入 `error`，不会再“假成功”。

---

## 一、支持的文档类型

| 文件类型 | 扩展名 | 解析器 | 说明 |
|---------|--------|--------|------|
| PDF | `.pdf` | `PdfParser` | 提取文字页；若 `extract_images=True` 同时提取嵌入图片并调 Vision 描述 |
| Word | `.docx` | `DocxParser` | 提取段落 + 表格 |
| Markdown | `.md` | `MarkdownParser` | 按标题分块 |
| 纯文本 | `.txt` | `TxtParser` | — |
| CSV | `.csv` | `CsvParser` | 每行转为文本 |
| QA | — | `QaPairParser` | Q+A 对直接入库 |
| **PPT** | `.pptx` | **`PptxParser`**（M263 新增） | 按幻灯片提取文字框 + 备注 |
| **图片** | `.jpg/.jpeg/.png/.webp/.gif` | **`ImageParser`**（M263 新增） | 调 VisionDescriber 生成描述 |
| **音频** | `.mp3/.wav/.m4a/.flac/.aac` | **`AudioParser`** | 调 AudioDescriber 生成文本；若无文本则文档失败 |
| **视频** | `.mp4/.webm/.mov/.avi/.mkv` | **`VideoParser`** | 调 VideoDescriber 生成文本；若无文本则文档失败 |

---

## 二、VisionDescriber

**文件：** `backend/app/ai/rag/vision_describer.py`

### 职责

为图片生成文字描述，供后续 text embedding 使用。任何异常均静默处理（返回 `""`），不中断文档处理流程。

### Vision 模型选取优先级

1. `knowledge_base.vision_model_id`（管理员显式配置）
2. 平台第一个 `is_active=True & supports_vision=True & type='chat'` 的模型（`order by id asc`）
3. 无可用模型 → 返回 `""`，记录 warning

### 限制

| 限制项 | 值 |
|--------|-----|
| 单图最大 | 20 MB |
| Vision 调用超时 | 30 秒 |
| 小图过滤（PDF 嵌入图片） | < 4 KB 跳过（噪点/装饰图） |

### 调用方式

```python
from app.ai.rag.vision_describer import VisionDescriber

describer = VisionDescriber(db, tenant_id)
description = await describer.describe_image(
    image_bytes=b"...",
    mime_type="image/jpeg",
    knowledge_base=kb,   # 含可选 vision_model_id 属性
)
```

---

## 三、Audio / Video 当前真实状态

### Parser factory 已接入

- `get_parser()` 已将 `_AUDIO_TYPES -> AudioParser`
- `get_parser()` 已将 `_VIDEO_TYPES -> VideoParser`

### 处理结果策略

- `processor.py` 在音频/视频最终拿不到文本时，会抛出明确业务错误：
  - `knowledge_base.document.error.audio_text_unavailable`
  - `knowledge_base.document.error.video_text_unavailable`
- 这类文档会进入 `error` 状态，避免“上传成功但 0 chunk”的伪成功

### 开发约束

- 如果要宣称“多模态知识库已支持音频/视频”，不能只接 parser factory
- 必须同时保证 `AudioDescriber` / `VideoDescriber` 在当前部署环境可稳定产出文本
- 若描述器仍为占位实现，产品文案必须写成“管线已接入 / 依赖可用模型”

---

## 四、知识库配置（KnowledgeBase 字段）

| 字段 | 类型 | 说明 |
|------|------|------|
| `vision_model_id` | FK → ai_models \| null | Vision 描述使用的模型（null 时自动选取） |
| `audio_model_id` | FK → ai_models \| null | 音频描述 / 转写模型（null 时自动选取） |
| `video_model_id` | FK → ai_models \| null | 视频描述 / 理解模型（null 时自动选取） |
| `extract_images` | bool（默认 false） | 是否提取 PDF/文档中的嵌入图片 |
| `chunk_strategy` | enum | 支持 `recursive / sentence / semantic / paragraph` |
| `search_mode/top_k/score_threshold` | 列保留 | **已降级为历史字段**，运行时以 `Agent.rag_config` 为准 |

### 配置路径（管理端）

管理端 / 企业端 → AI → 知识库 → 创建/编辑 → Vision / Audio / Video 模型、分块策略等

---

## 五、文档处理流程（processor.py）

### VisionDescriber 实例化规则

```python
# 两种情况必须创建 VisionDescriber：
# 1. kb.extract_images=True → PDF 嵌入图片也需描述
# 2. 文档本身是图片文件 → 无论 extract_images 设置，都必须描述

_IMAGE_DOC_TYPES = frozenset({"image", "jpg", "jpeg", "png", "webp", "gif"})
_needs_vision = (
    kb is not None and kb.extract_images
) or doc.file_type in _IMAGE_DOC_TYPES
```

**重要**：`extract_images` 仅控制是否提取 PDF 内嵌图片。用户显式上传的图片文件始终走 Vision 描述，无需开启 `extract_images`。

### 空 ParsedPage 过滤

```python
return [p for p in pages if p.content.strip()]
```

Vision 描述失败（`description = ""`）时，`ImageParser` 返回空内容 `ParsedPage`，`processor.py` 会将其过滤掉，不进入分块阶段。

---

## 六、分块策略（chunker.py）

### 当前策略语义

- `recursive`：按标题 / 段落 / 句子递归切分，通用默认
- `sentence`：保留句边界，适合 FAQ、制度条文、短段落
- `semantic`：已升级为**结构感知分块**，优先按标题 / 列表 / 表格 / 段落切分，再对超长块回退句级或递归切分
- `paragraph`：按自然段落切分

### 关键结论

- 旧的“semantic 只是句边界 chunking”认知已经过时
- 如果想打“现代 RAG”卖点，默认建议优先评估 `semantic` 或 `sentence`

---

## 七、检索架构（retriever.py / rag_injector.py）

### 运行时配置中心

- 检索参数统一以 `Agent.rag_config` 为准：
  - `search_mode`
  - `top_k`
  - `score_threshold`
  - `rewrite_strategy`
  - `reranker_enabled`
  - `context_token_ratio`
- `KnowledgeBase.search_mode/top_k/score_threshold` 仅保留兼容，不再是运行时真源

### 多 Knowledge Base 检索

- 不再假设多个 KB 共享同一 embedding model / dimension
- 运行时改为**按 KB 独立生成 query embedding、独立召回、全局融合**
- `rag_injector.py` 不再选择单个 `primary_kb` 代表全部 KB

### 融合策略

- 当前融合采用 **per-KB recall + weighted RRF**
- `AgentKnowledgeBaseBinding.weight` 已真正接入融合，不再只是存储字段
- 权重作为**先验偏置**而非硬覆盖：
  - 高权重 KB 更容易进入前列
  - 但不会让低相关内容直接压过高相关内容

### 关键词检索增强

- PostgreSQL FTS 作为 baseline
- 额外叠加：
  - exact phrase boost
  - heading boost
  - filename boost
  - 中文 token / bigram 命中增强

---

## 八、Agent 绑定 UI / API

- Agent 详情页需暴露 `rag_config` 可配置 UI（tenant / admin 均应覆盖）
- KB 绑定列表需展示：
  - `kb_embedding_model_name`
  - `kb_embedding_dimensions`
  - `kb_chunk_strategy`
  - `weight` 的融合提示
- 版本快照 / diff 必须覆盖 `rag_config`

---

## 九、PdfParser 图片提取规则

- 逐页调用 `page.get_images(full=True)`
- 跳过 < 4 KB 的图片（噪点/分隔线/水印等装饰图）
- 每张图生成独立 `ParsedPage`，metadata 含 `{"type": "image", "page": N, "image_index": i}`
- 文字页和图片描述页共存于同一页码

---

## 十、PptxParser 提取规则

- 按幻灯片顺序提取
- 内容来源：文字框（`shape.text_frame`）+ 备注（`notes_slide.notes_text_frame`）
- metadata：`{"slide": N, "source": file_name}`
- 空幻灯片（无文字）跳过
- 依赖：`python-pptx`（已列入 `pyproject.toml`）

---

## 十一、前端支持

### 知识库表单新增字段

```typescript
// admin/tenant 知识库表单
visionModelId: null | number    // Vision 模型选择
audioModelId: null | number     // 音频模型选择
videoModelId: null | number     // 视频模型选择
extractImages: boolean           // 提取图片内容开关
```

### 上传文件类型扩展

`ALLOWED_EXTENSIONS` 新增：`.pptx`, `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, 音频、视频扩展名

### 响应新增字段

```typescript
// KnowledgeBaseInfo 接口新增
vision_model_name: null | string   // 已配置的 Vision 模型名称

// AgentKBBindingInfo / AIAgentKBBindingInfo 新增
kb_embedding_model_name: null | string
kb_embedding_dimensions: null | number
kb_chunk_strategy: null | string
```

---

## 十二、i18n Keys

### 后端（`backend/app/locales/`）

```json
{
  "knowledge_base": {
    "vision": {
      "describe_prompt": "请详细描述这张图片的内容..."
    },
    "document": {
      "error": {
        "audio_text_unavailable": "...",
        "video_text_unavailable": "..."
      }
    }
  }
}
```

### 前端

| Key | 位置 |
|-----|------|
| `admin.ai.knowledgeBase.visionModelId` | zh-CN/en-US admin/ai.json |
| `admin.ai.knowledgeBase.extractImages` | zh-CN/en-US admin/ai.json |
| `tenant.ai.knowledgeBase.visionModelId` | zh-CN/en-US tenant/ai.json |
| `tenant.ai.knowledgeBase.extractImages` | zh-CN/en-US tenant/ai.json |
| `tenant.knowledgeBase.field.chunkStrategySentence` | zh-CN/en-US tenant/knowledgeBase.json |
| `admin.ai.agent.knowledgeBase.*` | zh-CN/en-US admin/ai.json |
| `tenant.ai.agent.knowledgeBase.*` | zh-CN/en-US tenant/ai.json |

---

## 十三、迁移文件

```
20260228_0bc08d7f8260_add_vision_model_id_and_extract_images_to_knowledge_bases.py
```

- 新增 `knowledge_bases.vision_model_id`（FK → ai_models，ON DELETE SET NULL）
- 新增 `knowledge_bases.extract_images`（Boolean，server_default=false）
- 创建索引 `ix_knowledge_bases_vision_model_id`
- **FK 约束名必须显式命名**（禁止传 `None`，否则 downgrade 无法找到约束）

---

## 十四、关键文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/ai/rag/vision_describer.py` | Vision 图片描述服务 |
| `backend/app/ai/rag/parser.py` | 文件解析器（含 Image / Audio / Video / Pptx） |
| `backend/app/ai/rag/processor.py` | 文档处理编排（Vision / Audio / Video 实例化与错误策略） |
| `backend/app/ai/rag/chunker.py` | `recursive / sentence / semantic / paragraph` 分块实现 |
| `backend/app/ai/rag/retriever.py` | per-KB recall + weighted RRF + 中文 keyword 增强 |
| `backend/app/ai/rag_injector.py` | Agent 级 RAG 注入（多 KB 校验 + 运行时 rag_config） |
| `backend/app/models/ai/knowledge_base.py` | KnowledgeBase ORM（vision_model_id / extract_images） |
| `backend/app/schemas/ai/knowledge_base.py` | 知识库 Schema（含新字段） |
| `backend/migrations/versions/20260228_0bc08d7f8260_*.py` | Alembic 迁移文件 |
