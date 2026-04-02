# AI 富文本编辑器实施审计报告

**审计日期**：基于当前代码快照  
**对照文档**：规划「AI 富文本编辑器强化与修复」P0/P1/P2 及实施顺序

---

## 一、P0 项审计结果

### P0-1：NovusDoc 与平台编辑器操作合并竞态

| 检查项 | 状态 | 说明 |
|--------|------|------|
| appendPageOperations 存在且语义正确 | 通过 | page-operation-registry.ts：追加到 current，cleanup 仅按 appendedNames 过滤移除；JSDoc 含 Contract 约定说明。 |
| 导出与插件 API 暴露 | 通过 | ai-slide-panel/index.ts 导出 appendPageOperations；plugin-shared.ts 的 export、API 类型、exposePluginShared 均包含。 |
| DocumentEditor 使用 append 而非 register 合并 | 通过 | DocumentEditor.vue：仅调用 shared.appendPageOperations(editorPageKey.value, documentOps)。 |
| 等待平台 ops 后再 append | 通过 | onMounted 内顺序：nextTickMount() → nextTick() → waitForEditorPageOps() → setupEditorPageAwareness()。 |
| waitForEditorPageOps 逻辑 | 通过 | 轮询 listPageOperations(key) 直至存在 get_editor_html，80ms 间隔，上限 2s；超时后 console.warn。 |
| nextTickMount 注释 | 通过 | 已注释：「Brief delay so the editor container is ready before mounting RichTextEditor」。 |

### P0-2：replace_content 表格属性清洗

| 检查项 | 状态 | 说明 |
|--------|------|------|
| replace_content 使用 sanitizeTableAttributesForSetContent | 通过 | useEditorPageOps.ts：replace_content handler 中 html = sanitizeTableAttributesForSetContent(fixTableWidthZero(ensureHtml(raw)))，再 setContent。 |

---

## 二、P1 项审计结果

### P1-3：replace_section 的 i18n

| 检查项 | 状态 | 说明 |
|--------|------|------|
| label 使用 $t | 通过 | useEditorPageOps.ts：label: $t('common.replaceSection')。 |
| common.replaceSection 中英文 | 通过 | zh-CN、en-US 的 common.json 中均有 replaceSection。 |

### P1-4：编辑器内 AI 流式「停止生成」与错误反馈

| 检查项 | 状态 | 说明 |
|--------|------|------|
| useEditorAI 暴露 aiError、retryAI、canRetry | 通过 | aiError ref；streamAI 内 event.error/onError/catch 赋值 aiError；retryAI()；canRetry 在首次 streamAI 时置 true；acceptResult/discardResult 清空 aiError。 |
| 停止按钮与 cancelAI | 通过 | AIResultPanel v-if="loading" 时展示停止按钮 @stop；RichTextEditor 两处 @stop="cancelAI"。 |
| 错误展示与重试 | 通过 | AIResultPanel 接收 error、canRetry；v-if="error" 显示错误文案与重试按钮；重试按钮 :disabled="!canRetry"。 |
| 面板在 loading/error 时可见 | 通过 | 两处 AIResultPanel 的 v-if 均为 ai && (aiResult \|\| aiError \|\| aiLoading)。 |
| common.stopGeneration | 通过 | zh-CN / en-US 的 common.json 中均有 stopGeneration。 |

### P1-5：get_editor_html 截断在 page_data 中的说明

| 检查项 | 状态 | 说明 |
|--------|------|------|
| entity_description 含截断与 old_html 说明 | 通过 | useEditorPageOps.ts registerPageContext 的 entity_description 已含「长文档时 get_editor_html 返回可能被截断…短且唯一的 HTML 片段…勿用整篇作为 old_html」。 |

---

## 三、P2 项审计结果

### P2-6：insert_content / append_content 含表格时的稳健性

| 检查项 | 状态 | 说明 |
|--------|------|------|
| insert_content 表格清洗 | 通过 | handler 中 html = sanitizeTableAttributesForSetContent(fixTableWidthZero(ensureHtml(raw)))，再 insertContent。 |
| append_content 表格清洗 | 通过 | 同上管道后 insertContentAt。 |

### P2-7：AI 气泡菜单与结果面板的无障碍

| 检查项 | 状态 | 说明 |
|--------|------|------|
| AIBubbleMenu 格式按钮 aria-label | 通过 | :aria-label="$t(\`common.${act.key}\`)"。 |
| AIBubbleMenu AI 按钮 aria-label | 通过 | :aria-label="$t(act.labelKey)"。 |
| AIResultPanel 按钮 aria-label | 通过 | 停止、重试、丢弃、纯文本、带格式按钮均带 :aria-label。 |

### P2-8：DocumentEditor 的 50ms 延迟可读性

| 检查项 | 状态 | 说明 |
|--------|------|------|
| nextTickMount 注释 | 通过 | 已注释 50ms 用途。 |

---

## 四、一致性检查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| replace_section label 与 i18n 一致 | 通过 | common.replaceSection，中英文已配置。 |
| 写入类 op 的 HTML 管道一致 | 通过 | replace_content、replace_section、insert_content、append_content 均经 ensureHtml（或 + normalizeHtmlForMatch）、fixTableWidthZero、sanitizeTableAttributesForSetContent。 |
| RichTextEditor full/compact 两处 AI 对等 | 通过 | 两处 AIResultPanel 的 props/events 一致（result、loading、error、canRetry、stop、retry、accept、discard）。 |

---

## 五、审计结论

- **P0/P1/P2 规划项**：均已按规划实现，与文档描述一致。
- **可选改进**（已落实）：append 约定注释、waitForEditorPageOps 超时 console.warn、无 lastStreamFeature 时重试按钮禁用（canRetry）。
- **依赖与导出**：appendPageOperations 的注册表、ai-slide-panel 导出、plugin-shared 导出与类型、DocumentEditor 的 shared 类型与调用均正确。

**总体**：实施通过审计，无需强制修改。

---

## 六、深度审计（边界、错误路径、安全与一致性）

### 6.1 边界与健壮性

| 项 | 结论 | 说明 |
|----|------|------|
| replace_section 空/极短 old_html | 已防护 | 入口校验 `if (!oldSnippet) return`，oldSnippet 为 trim 后值；若 LLM 传仅空白或仅实体（如 `&nbsp;`）经 normalize 后变为极短串，可能匹配到文档中首处空格等，属极端输入，当前未再做 normOld 长度校验，可接受。 |
| replace_section 仅替换首次出现 | 符合设计 | `normCurrent.replace(normOld, newHtmlClean)` 仅替换第一次；描述已要求 old_html 为「short unique HTML fragment」，行为与规划一致。 |
| get_editor_html 截断边界 | 已知限制 | `html.slice(0, 8000)` 可能在标签中间截断，返回片段非合法 HTML；LLM 若用「短且唯一片段」做 replace_section 的 old_html 仍可用。可选改进：在 8000 内向后找最近 `>` 再截断，减少断标签。 |
| insert_content / append_content 空 content | 已防护 | `if (!raw) return { success: false, message: 'No content provided' }`。 |
| replace_content 空 content | 未显式校验 | `String(params.content \|\| '')` 后若 raw 为空会 setContent('')，清空编辑器；与「全文替换」语义一致，可接受。 |

### 6.2 错误与异步行为

| 项 | 结论 | 说明 |
|----|------|------|
| cancelAI / AbortError | 正确 | catch 中判断 `(err as Error).name !== 'AbortError'` 才设置 aiError；用户主动停止不展示错误。 |
| cancelAI 后 aiResult | 有意保留 | 不清空 aiResult，用户可见已生成部分；符合「停止生成」预期。 |
| streamAI 中 event.error | 已处理 | 设置 aiError 并 return，finally 中 aiLoading = false、abortController = null。 |
| retryAI 传参 | 安全 | lastStreamExtra 在 streamAI 入口用 `{ ...extra }` 快照，retry 时传该快照，无共享可变引用。 |
| useEditorPageOps 清理时机 | 正确 | onBeforeUnmount 中 cleanupOps?.()、cleanupCtx?.()、unwatch()；editorRef 变为 undefined 时 watch 不调用 register（仅 `if (ed) register()`），依赖组件卸载时统一清理，与当前用法一致。 |

### 6.3 安全（XSS / 不可信 HTML）

| 项 | 结论 | 说明 |
|----|------|------|
| AIResultPanel v-html | 风险可控 | 使用 `md.render(props.result)`，MarkdownIt 未开 html 时会对 HTML 转义；result 来自 SSE 流，若后端不做额外净化，极端输出仍可能经 Markdown 语法影响展示，建议保持 html: false。 |
| 页面操作写入 HTML | 依赖 TipTap | replace_section / replace_content / insert_content 的 new_html 来自 LLM；TipTap setContent/insertContent 会解析 HTML，依赖其及扩展的默认行为；规划已列「可选：DOMPurify 或白名单」为加固项，当前未引入。 |

### 6.4 插件与宿主契约

| 项 | 结论 | 说明 |
|----|------|------|
| DocumentEditor 无 appendPageOperations | 降级 | shared?.appendPageOperations 为假时不调用，document ops 不注册，仅保留平台编辑器 ops；属宿主契约，可接受。 |
| waitForEditorPageOps 无 listPageOperations | 直接通过 | list 为假时直接 return，随后 setupEditorPageAwareness 仍会执行 append（若 shared.appendPageOperations 存在）；若 list 不存在但 append 存在，会 append 到当前列表（可能为空），平台后续 register 会覆盖，与规划一致。 |
| listPageOperations 返回结构 | 类型兼容 | DocumentEditor 仅用 `ops.some((o) => o.name === 'get_editor_html')`，依赖 `{ name: string }[]`；registry 返回 PageOperation[]，含 name，兼容。 |

### 6.5 无障碍与展示

| 项 | 结论 | 说明 |
|----|------|------|
| AIResultPanel 错误 + 结果同屏 | 合理 | 有 error 时显示错误文案，下方仍显示 result（可能为部分结果）；布局与交互合理。 |
| 重试按钮禁用 | 已实现 | canRetry 在首次 streamAI 时置 true，无上次请求时重试按钮 disabled，避免无效点击。 |
| 气泡菜单焦点 | 未强制 | 未发现气泡展开时焦点自动移入或 Esc 回编辑器；规划中为 P2 可选，当前未实现，可后续增强。 |

### 6.6 建议与可选改进（非必须）

1. **get_editor_html 截断**：在 8000 字符内向后查找最后一个 `>` 再截断，尽量不截断标签，减少无效 HTML 片段。
2. **replace_section**：若需更稳妥，可对 `normOld` 做最小长度校验（如 length >= 3），避免单字符或空串误匹配。
3. **XSS 加固**：对来自 LLM 的 HTML 在 setContent/insertContent 前增加白名单或 DOMPurify（仅该路径），作为可选安全增强。
4. **气泡菜单键盘**：气泡展开时焦点移入第一按钮、Esc 关闭并焦点回编辑器，提升键盘与读屏体验。
