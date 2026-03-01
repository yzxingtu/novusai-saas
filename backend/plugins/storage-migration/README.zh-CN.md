# 存储迁移工具

NovusAI SaaS 平台跨存储驱动文件迁移工具。

## 功能特性

- **影响分析**：切换存储前分析文件数量、大小和可见性分布
- **双向迁移**：支持 local、aliyun-oss、amazon-s3、tencent-cos、qiniu-kodo 之间的任意迁移
- **批量处理**：可配置并发数（1-20）的并发文件传输
- **断点续传**：支持暂停/恢复，中断后可继续
- **回滚机制**：迁移完成后可回滚 DB 记录到原始驱动
- **源文件清理**：迁移成功后可选择删除源存储中的旧文件

## API 端点

所有端点仅限管理员，通过以下路径访问：
`/admin/plugins/storage-migration/api/...`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `impact-analysis` | 存储切换前影响分析 |
| POST | `tasks` | 创建并启动迁移任务 |
| GET | `tasks` | 迁移任务列表（历史记录） |
| GET | `tasks/{task_id}` | 任务详情含进度 |
| POST | `tasks/{task_id}/pause` | 暂停运行中的任务 |
| POST | `tasks/{task_id}/resume` | 恢复已暂停的任务 |
| POST | `tasks/{task_id}/cancel` | 取消任务 |
| POST | `tasks/{task_id}/retry-failed` | 重试失败文件 |
| POST | `tasks/{task_id}/rollback` | 回滚已完成的迁移 |
| DELETE | `tasks/{task_id}/source-files` | 删除源存储中的旧文件 |

## 使用方法

1. 安装并启用插件
2. 进入管理后台 **系统设置 > 存储管理**
3. 使用 **影响分析** 检查切换前的影响
4. 创建迁移任务，指定源驱动和目标驱动
5. 在迁移管理页面监控进度
6. 完成后可选择清理源文件

## 前提条件

- 至少需要两个存储驱动可用（对应插件已安装并启用）
- 所有操作需要管理员权限
