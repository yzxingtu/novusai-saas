# 模型多模态使用规范 / Multimodal Model Usage

> 约定 Vision / Audio / Video 多模态能力在「对话适配器」「知识库配置」「RAG 描述器」中的使用方式与选型规则。
> Conventions for vision/audio/video in chat adapter, knowledge base config, and RAG describers.

---

## 一、能力字段（AIModel）

| 字段 | 类型 | 说明 |
|------|------|------|
| `supports_vision` | bool | 是否支持图像输入（对话 image_url、RAG VisionDescriber） |
| `supports_audio` | bool | 是否支持音频输入（对话 input_audio、RAG AudioDescriber/ASR） |
| `supports_video` | bool | 是否支持视频输入（对话待厂商扩展、RAG VideoDescriber） |

- 用于**对话**：调用 Adapter 前根据当前选用模型的上述字段传入 `supports_vision` / `supports_audio` / `supports_video`，决定附件如何转换（原生块 vs 文字提示）。
- 用于**知识库**：列表/筛选可按能力过滤；KB 可选「Vision / 音频 / 视频」模型时，仅展示对应能力为 True 的模型。
- 新增能力字段时需同步：Model 表与迁移、Schema、前端模型选择 API 过滤条件、Adapter 与 RAG 选模型逻辑。

---

## 二、对话侧（OpenAI Adapter）

**文件：** `backend/app/ai/adapters/openai_adapter.py`

### 2.1 入参

- `_convert_messages(..., supports_vision=True, supports_audio=False, supports_video=False)`  
  由调用方根据**当前使用的 chat 模型**的 `supports_vision` / `supports_audio` / `supports_video` 传入，不从请求体猜测。

- `chat()` / `stream_chat()` 内从 `kwargs` 中 `pop` 上述三个标志并传入 `_convert_messages`，不把标志传给下游 API。

### 2.2 图片（image）

- `att_type == "image"` 且 `att_url` 存在：
  - **supports_vision=True**：追加 `image_url` 块。
  - **supports_vision=False**：追加文字提示 `[Image: 文件名]`。
- 无 URL 的图片附件不追加 content（与现有逻辑一致）。

### 2.3 音频（audio）

- **supports_audio=False** 或未提供 URL：一律追加文字提示 `[Audio: 文件名]`。
- **supports_audio=True** 且适配器启用原生音频（如 `SUPPORTS_NATIVE_AUDIO=True`）且 **att_url 存在且非空**：
  - 支持 **data URL**（`data:audio/xxx;base64,...`）与 **HTTP GET**。
  - URL 拉取：`_fetch_audio_bytes`，超时与最大字节数使用常量（如 30s、25MB）；解析响应头 `Content-Length` 时做安全解析（避免非数字/空串导致异常）。
  - 成功取得字节 → base64 + MIME→format 映射（见 `_AUDIO_MIME_TO_OPENAI_FORMAT`）→ 追加 `input_audio` 块。
  - 拉取失败、超大小、无 URL、url 为 null 或 key 缺失：追加文字提示 `[Audio: 文件名]`。
- **禁止魔法字符串**：MIME→format 映射、超时、最大字节数均用常量或字典配置。

### 2.4 视频（video）

- 当前**仅支持文字提示**：`[Video: 文件名]`。不向 API 传原生 video 块。
- 若后续厂商支持原生 video，再在 `att_type == "video"` 分支扩展；扩展时仍根据 `supports_video` 决定是否传原生块。

### 2.5 其他附件（file）

- 无原生块：仅追加文字提示 `[Attached file: 文件名, type: mime]`。

---

## 三、知识库可选模型（KnowledgeBase）

| 字段 | 类型 | 说明 |
|------|------|------|
| `vision_model_id` | FK → ai_models \| null | 图片描述使用的模型（null 表示自动选取） |
| `audio_model_id` | FK → ai_models \| null | 音频描述/ASR 使用的模型（null 表示自动选取） |
| `video_model_id` | FK → ai_models \| null | 视频描述使用的模型（null 表示自动选取） |

- **列表/详情/创建/更新**：返回或提交时需包含 `*_model_id` 及展示用 `*_model_name`（由 API/Service 从关联 model 组装，getattr 保护）。
- **删除依赖**：`AIModel.__delete_deps__` 中需包含对 `knowledge_base.vision_model_id` / `audio_model_id` / `video_model_id` 的 NULLIFY，避免删除模型时破坏 FK；前端删除依赖提示文案需在 `common.dependency.model` 中配置（如 `knowledge_base_vision` / `knowledge_base_audio` / `knowledge_base_video`）。

---

## 四、RAG 描述器选模型优先级

三种描述器（Vision / Audio / Video）采用**统一优先级**：

1. **知识库显式配置**：`kb.vision_model_id` / `kb.audio_model_id` / `kb.video_model_id` 非空且对应模型存在、is_active、且具备对应能力（supports_vision / supports_audio / supports_video）。
2. **平台默认**：平台第一个「is_active + 对应能力 + type=chat」的模型（按 id 升序取一条）。
3. **无可用模型**：返回 `""`，不抛异常；调用方（如 processor）会过滤空内容。

### 4.1 VisionDescriber

- 见 [multimodal-rag.md](multimodal-rag.md)：`describe_image(image_bytes, mime_type, knowledge_base)`，选模型逻辑同上。

### 4.2 AudioDescriber

- **文件：** `backend/app/ai/rag/audio_describer.py`
- `_get_audio_model(kb)`：优先 `kb.audio_model_id` 且 `supports_audio=True`，否则平台首个 supports_audio 的 chat 模型。
- `describe_audio(...)`：无模型或占位未接入 ASR 时返回 `""`；单条音频大小超限（如 50MB）返回 `""` 并打 warning。

### 4.3 VideoDescriber

- **文件：** `backend/app/ai/rag/video_describer.py`
- `_get_video_model(kb)`：优先 `kb.video_model_id` 且 `supports_video=True`，否则平台首个 supports_video 的 chat 模型。
- `describe_video(...)`：无模型或占位未接入视频理解时返回 `""`；单条视频大小超限（如 100MB）返回 `""` 并打 warning。

---

## 五、前端约定

### 5.1 知识库表单

- 管理端/企业端知识库创建/编辑：提供 **Vision 模型**、**音频模型**、**视频模型** 三列下拉（可为空，表示「自动」）。
- 下拉选项：仅列出对应能力为 True 的模型（`supports_vision` / `supports_audio` / `supports_video`），且可加一项「自动」占位（value 为 null）。
- 表单默认值：`getFormDefaults()` 中必须包含 `vision_model_id: null`、`audio_model_id: null`、`video_model_id: null`，与后端 Schema 一致。

### 5.2 模型选择 API

- 列表/筛选接口返回的模型对象中需包含 `supports_vision` / `supports_audio` / `supports_video`，供前端过滤「可选 Vision/音频/视频模型」。
- 前端类型（如 `api/tenant/ai.ts`）中模型类型需声明上述三个可选字段，与后端一致。

### 5.3 类型与契约

- 知识库相关请求/响应 TypeScript 类型需与后端 Schema 一致：含 `vision_model_id` / `audio_model_id` / `video_model_id` 及对应 `*_model_name`、`extract_images` 等，便于类型安全与后续契约变更。

---

## 六、检查清单（多模态相关）

### 后端

- [ ] AIModel 表含 `supports_vision` / `supports_audio` / `supports_video`，且已在 __filterable__ 等处声明
- [ ] 知识库 Model/Schema 中 vision/audio/video 三组字段齐全（含 FK、nullable、索引）
- [ ] AIModel.__delete_deps__ 含 knowledge_base_vision / knowledge_base_audio / knowledge_base_video 的 NULLIFY
- [ ] 所有返回 KB 的接口（list/create/update/detail）对 result 写入 vision_model_name、audio_model_name、video_model_name（getattr 保护）
- [ ] Adapter 中音频 URL 拉取使用常量超时与大小限制，Content-Length 做安全解析
- [ ] RAG 描述器选模型：KB 显式 id 优先，再平台首个对应能力模型；无模型返回 `""`

### 前端

- [ ] 知识库表单三列模型选择 + getFormDefaults() 含 vision/audio/video 的 null 默认值
- [ ] 模型选择选项按 supports_vision / supports_audio / supports_video 过滤
- [ ] 知识库 API 类型与后端契约一致（含 vision/audio/video 及 *_model_name、extract_images）

### 文档与 i18n

- [ ] [deletion-deps.md](deletion-deps.md) 与前端 `common.dependency.model` 的 `knowledge_base_audio`、`knowledge_base_video` 等 key 已配置
- [ ] 知识库相关 locale（admin/tenant）含 vision/audio/video 的 field 与 help 文案

---

## 七、相关文档

| 文档 | 说明 |
|------|------|
| [multimodal-rag.md](multimodal-rag.md) | 多模态 RAG（文档类型、解析器、VisionDescriber、KB vision_model_id / extract_images） |
| [ai-module.md](ai-module.md) | AI 模块整体架构与网关/技能链路 |
| [deletion-deps.md](deletion-deps.md) | 删除依赖与 NULLIFY 声明 |
