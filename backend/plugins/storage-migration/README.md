# Storage Migration Tool

Cross-driver storage file migration tool for NovusAI SaaS platform.

## Features

- **Impact Analysis**: Analyze file counts, sizes, and visibility breakdown before switching storage drivers
- **Bidirectional Migration**: Support migration between local, aliyun-oss, amazon-s3, tencent-cos, and qiniu-kodo
- **Batch Processing**: Concurrent file transfer with configurable parallelism (1-20)
- **Resume Capability**: Pause/resume migrations, surviving interruptions
- **Rollback**: Revert DB records to original driver after migration
- **Source Cleanup**: Optionally delete source files after successful migration

## API Endpoints

All endpoints are admin-only, accessed via:
`/admin/plugins/storage-migration/api/...`

| Method | Path | Description |
|--------|------|-------------|
| GET | `impact-analysis` | Analyze impact before storage switch |
| POST | `tasks` | Create and start a migration task |
| GET | `tasks` | List migration tasks (history) |
| GET | `tasks/{task_id}` | Get task detail with progress |
| POST | `tasks/{task_id}/pause` | Pause a running task |
| POST | `tasks/{task_id}/resume` | Resume a paused task |
| POST | `tasks/{task_id}/cancel` | Cancel a task |
| POST | `tasks/{task_id}/retry-failed` | Retry failed files |
| POST | `tasks/{task_id}/rollback` | Rollback completed migration |
| DELETE | `tasks/{task_id}/source-files` | Delete source files after migration |

## Usage

1. Install and enable the plugin
2. Go to **System Settings > Storage** in admin panel
3. Use **Impact Analysis** to check files before switching
4. Create a migration task specifying source and target drivers
5. Open **Admin > System Management > Storage Migration** to monitor progress
6. After completion, optionally clean up source files

## Requirements

- At least two storage drivers must be available (plugins installed and enabled)
- Admin privileges required for all operations
