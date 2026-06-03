# 文件下载规范 / File Download Specification

> 当需要实现「从后端获取文件并触发浏览器下载」功能时，必须遵循本规范，避免 Blob 被响应拦截器误判、下载不触发等常见问题。

---

## 一、问题背景

### 典型故障：请求成功但浏览器不下载

**根因**：`requestClient` 的响应拦截器 `createResponseDataInterceptor` 默认按业务 JSON 格式解析（`code`/`data`），当响应为 Blob 时：

```ts
// 拦截器尝试从 Blob 提取 code
const code = responseData?.[codeField];  // blob['code'] → undefined
if (code === successCode) {               // undefined !== 0 → 视为错误
  return responseData[dataField];
}
throw Object.assign({}, response, { response });  // 抛出！
```

导致 Blob 被当作业务错误抛出，`downloadBlob` 从未执行。

---

## 二、正确用法

### 2.1 平台页面（web-antd 主应用）

使用 `requestClient.download` + `downloadBlob`：

```typescript
import { message } from 'ant-design-vue';
import { requestClient } from '#/utils/request';
import { downloadBlob } from '#/utils/download';

async function handleExport() {
  try {
    const blob = await requestClient.download<Blob>(`/admin/xxx/export?format=pdf`);
    downloadBlob(blob, { filename: `report-${Date.now()}.pdf` });
  } catch (e) {
    message.error((e as Error)?.message ?? '下载失败');
  }
}
```

**关键**：`requestClient.download` 内部已设置 `responseReturn: 'raw'`，拦截器会返回完整 AxiosResponse，`response.data` 正确得到 Blob。

### 2.2 插件（NovusDoc 等 UMD 插件）

插件不能直接导入宿主模块，必须通过 `NovusPluginShared` 获取 `downloadBlob` 和 `requestClient`：

```typescript
// 在插件组件中
const shared = (window as unknown as Record<string, unknown>).NovusPluginShared as {
  requestClient: { download: (url: string) => Promise<Blob> };
  downloadBlob?: (blob: Blob, opts: { filename: string }) => void;
} | undefined;

async function onExport(format: 'html' | 'md' | 'pdf') {
  const downloadBlob = shared?.downloadBlob;
  if (!downloadBlob || !shared?.requestClient) {
    console.error('[Plugin] downloadBlob or requestClient not available');
    return;
  }
  try {
    // url: 导出接口相对路径，如 `/admin/plugins/novusdoc/api/docs/${id}/export?format=html`
    // title: 文件名前缀，如 doc.title
    const blob = await shared.requestClient.download(url);
    downloadBlob(blob, { filename: `${title}.${format}` });
  } catch {
    // 错误由 requestClient 统一 showMessage
  }
}
```

**禁止**：插件内手写 `URL.createObjectURL` + `<a download>` + `click()`，必须使用 `downloadBlob`，以兼容各浏览器及弹窗拦截。

---

## 三、requestClient.download 要求

`#/utils/request/request-client.ts` 的 `download` 方法**必须**在 `__options` 中包含：

```typescript
__options: {
  showErrorMessage: false,
  showCodeMessage: false,
  responseReturn: 'raw',   // 关键！跳过 code/data 解析
},
```

新增或修改 `download` 时，禁止删除 `responseReturn: 'raw'`。

---

## 四、后端文件响应

### 4.1 返回二进制（HTML/MD/PDF 等）

使用 Starlette `Response`，设置正确的 `media_type` 和 `Content-Disposition`：

```python
from starlette.responses import Response

return Response(
    content=bytes_or_str_content,
    media_type="text/html; charset=utf-8",  # 或 application/pdf、text/markdown 等
    headers={"Content-Disposition": _content_disposition_attachment(f"{safe_title}.html")},
)
```

### 4.2 Content-Disposition 与非 ASCII 文件名

HTTP 头必须是 Latin-1，中文等需用 RFC 5987：

```python
from urllib.parse import quote

def _content_disposition_attachment(filename: str) -> str:
    try:
        filename.encode("ascii")
        return f'attachment; filename="{filename}"'
    except UnicodeEncodeError:
        encoded = quote(filename, safe="")
        return f"attachment; filename=\"document\"; filename*=UTF-8''{encoded}"
```

---

## 五、常见错误与禁令

| 错误 | 正确做法 |
|------|----------|
| 用 `requestClient.get(url, { responseType: 'blob' })` 获取文件 | 用 `requestClient.download(url)` |
| 插件内手写 `a.click()` 触发下载 | 用 `NovusPluginShared.downloadBlob` |
| 修改 `download` 时去掉 `responseReturn: 'raw'` | 禁止，必须保留 |
| 新窗口 `window.open(exportUrl)` 打开下载链接 | 会 401（无 token），改用 `requestClient.download` 获取 Blob 后以 `downloadBlob` 触发 |
| 后端 `Content-Disposition` 直接写中文文件名 | 用 RFC 5987 `filename*=UTF-8''` |

---

## 六、相关文件

| 文件 | 作用 |
|------|------|
| `frontend/apps/web-antd/src/utils/request/request-client.ts` | `download` 方法（含 responseReturn: 'raw'） |
| `frontend/apps/web-antd/src/utils/download.ts` | `downloadBlob` 等工具函数 |
| `frontend/apps/web-antd/src/utils/plugin-shared.ts` | 向插件暴露 `downloadBlob` |
| `backend/plugins/novusdoc/backend/api/export.py` | 导出示例（Content-Disposition、PDF 预处理） |
