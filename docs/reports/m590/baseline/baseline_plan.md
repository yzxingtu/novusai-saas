# M590 基线与回滚计划

## 插件状态基线
- netdisk (id=1081): enabled
- weather-widget (id=1080): enabled
- tencent-cos (id=1079): disabled
- storage-migration (id=1078): enabled
- qiniu-kodo (id=1077): enabled
- novusdoc-pro (id=1076): enabled
- novusdoc (id=1075): enabled
- novus-crud-code (id=1074): enabled
- amazon-s3 (id=1073): disabled
- aliyun-oss (id=1072): installed

## 启用顺序（拓扑）
1. aliyun-oss
2. amazon-s3
3. netdisk
4. novus-crud-code
5. novusdoc
6. qiniu-kodo
7. storage-migration
8. tencent-cos
9. weather-widget
10. novusdoc-pro

## 计划清理的 Python 包（生效 marker）
- Pillow
- aiofiles
- alibabacloud-oss-v2
- anyio
- bcrypt
- boto3
- cos-python-sdk-v5
- httpx
- qiniu
- redis

## 计划清理的 npm 包
- @tiptap/extension-character-count
- @tiptap/extension-collaboration
- @tiptap/extension-collaboration-cursor
- @tiptap/extension-highlight
- @tiptap/extension-image
- @tiptap/extension-link
- @tiptap/extension-placeholder
- @tiptap/extension-table
- @tiptap/extension-table-cell
- @tiptap/extension-table-header
- @tiptap/extension-table-row
- @tiptap/extension-task-item
- @tiptap/extension-task-list
- @tiptap/extension-text-align
- @tiptap/extension-underline
- @tiptap/starter-kit
- @tiptap/vue-3
- @types/sortablejs
- @vue-flow/background
- @vue-flow/controls
- @vue-flow/core
- @vue-flow/minimap
- sortablejs
- vxe-table
- xe-utils
- y-protocols
- yjs

## 回滚方案
- Python 回滚：使用 `pip_freeze.txt` + `pip install -r` 恢复，或按插件启用链路自动回装。
- npm 回滚：按插件重启用触发 `pnpm add` 自动回装；必要时执行 `pnpm install` 基于 lock 恢复。
- 插件状态回滚：按 `plugin_status_api.json` 恢复原始 enabled/disabled。