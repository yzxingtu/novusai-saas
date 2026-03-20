# 多模态 RAG 规范（M263）

> 知识库支持图片/PDF 嵌入图片/PPTX 提取文字，通过 Vision 模型生成文字描述后纳入向量索引，实现图文混合检索。

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

## 三、知识库配置（KnowledgeBase 新字段）

| 字段 | 类型 | 说明 |
|------|------|------|
| `vision_model_id` | FK → ai_models \| null | Vision 描述使用的模型（null 时自动选取） |
| `extract_images` | bool（默认 false） | 是否提取 PDF/文档中的嵌入图片 |

### 配置路径（管理端）

管理端 → AI → 知识库 → 创建/编辑 → 「Vision 模型」+ 「提取图片内容」开关

---

## 四、文档处理流程（processor.py）

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

## 五、PdfParser 图片提取规则

- 逐页调用 `page.get_images(full=True)`
- 跳过 < 4 KB 的图片（噪点/分隔线/水印等装饰图）
- 每张图生成独立 `ParsedPage`，metadata 含 `{"type": "image", "page": N, "image_index": i}`
- 文字页和图片描述页共存于同一页码

---

## 六、PptxParser 提取规则

- 按幻灯片顺序提取
- 内容来源：文字框（`shape.text_frame`）+ 备注（`notes_slide.notes_text_frame`）
- metadata：`{"slide": N, "source": file_name}`
- 空幻灯片（无文字）跳过
- 依赖：`python-pptx`（已列入 `pyproject.toml`）

---

## 七、前端支持

### 知识库表单新增字段

```typescript
// admin/tenant 知识库表单
visionModelId: null | number    // Vision 模型选择
extractImages: boolean           // 提取图片内容开关
```

### 上传文件类型扩展

`ALLOWED_EXTENSIONS` 新增：`.pptx`, `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`

### 响应新增字段

```typescript
// KnowledgeBaseInfo 接口新增
vision_model_name: null | string   // 已配置的 Vision 模型名称
```

---

## 八、i18n Keys

### 后端（`backend/app/locales/`）

```json
{
  "knowledge_base": {
    "vision": {
      "describe_prompt": "请详细描述这张图片的内容..."
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

---

## 九、迁移文件

```
20260228_0bc08d7f8260_add_vision_model_id_and_extract_images_to_knowledge_bases.py
```

- 新增 `knowledge_bases.vision_model_id`（FK → ai_models，ON DELETE SET NULL）
- 新增 `knowledge_bases.extract_images`（Boolean，server_default=false）
- 创建索引 `ix_knowledge_bases_vision_model_id`
- **FK 约束名必须显式命名**（禁止传 `None`，否则 downgrade 无法找到约束）

---

## 十、关键文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/ai/rag/vision_describer.py` | Vision 图片描述服务 |
| `backend/app/ai/rag/parser.py` | 文件解析器（含 PptxParser / ImageParser） |
| `backend/app/ai/rag/processor.py` | 文档处理编排（VisionDescriber 实例化逻辑） |
| `backend/app/models/ai/knowledge_base.py` | KnowledgeBase ORM（vision_model_id / extract_images） |
| `backend/app/schemas/ai/knowledge_base.py` | 知识库 Schema（含新字段） |
| `backend/migrations/versions/20260228_0bc08d7f8260_*.py` | Alembic 迁移文件 |
