# 可观测性监控规范 / Observability Monitoring Specification

> Prometheus + Grafana 可观测性集成，仅限平台管理端（Admin）。

---

## 一、架构概览

```
Backend (FastAPI)
  ├── app/core/metrics.py         # 自定义 Prometheus 指标定义
  ├── app/middleware/metrics.py   # HTTP 请求指标中间件 + /metrics 端点
  └── app/api/admin/monitoring.py # /admin/monitoring/* 管理端 API

Prometheus → 抓取 /metrics (15s) → 存储时序
Grafana   → 连接 Prometheus → 预置 Dashboard 可视化
Admin 前端 → 实时概览(metrics-summary) + Grafana iframe 嵌入
```

**端隔离**：监控功能仅注册在 Admin 端，Tenant 和 User 端不暴露任何监控路由/菜单/API。

---

## 二、自定义业务指标

定义于 `app/core/metrics.py`：

| 指标名 | 类型 | 标签 | 埋点位置 |
|--------|------|------|----------|
| `novusai_ai_calls_total` | Counter | provider, model, status | AIGateway.chat/embedding/stream_chat |
| `novusai_ai_tokens_total` | Counter | provider, model, direction | AIGateway 成功回调 |
| `novusai_ai_latency_seconds` | Histogram | provider, model | AIGateway 成功/失败 |
| `novusai_celery_tasks_total` | Counter | task_name, status | BaseTask.on_success/on_failure |
| `novusai_celery_queue_length` | Gauge | queue_name | 后台 15s 采样任务 |
| `novusai_active_websockets` | Gauge | namespace | Socket.IO on_connect/on_disconnect |
| `novusai_active_tenants` | Gauge | - | 后台 15s 采样任务 |
| `novusai_db_pool_size` | Gauge | state | 后台 15s 采样任务 |

---

## 三、配置项

`app/core/config.py`：

| 配置 | 类型 | 说明 |
|------|------|------|
| `METRICS_ENABLED` | bool | 是否启用指标采集与 /metrics |
| `GRAFANA_URL` | str | Grafana 访问地址 |
| `GRAFANA_EMBED_URL` | str | iframe 嵌入 URL（含 dashboard ID） |
| `METRICS_ALLOWED_IPS` | str | Prometheus 拉取白名单（逗号分隔，空=允许所有） |

---

## 四、API 端点

| 路径 | 认证 | 说明 |
|------|------|------|
| `GET /metrics` | IP 白名单 | Prometheus 拉取（根路径） |
| `GET /admin/monitoring/metrics` | Admin | Prometheus 格式（管理端） |
| `GET /admin/monitoring/metrics-summary` | Admin | JSON 关键指标摘要 |
| `GET /admin/monitoring/grafana-config` | Admin | Grafana 嵌入配置 |

---

## 五、埋点规范

### 5.1 AIGateway

- 成功：`ai_calls_total.labels(..., status="success").inc()`；`ai_tokens_total`；`ai_latency_seconds.observe()`
- 失败：`ai_calls_total.labels(..., status="failure").inc()`；`ai_latency_seconds.observe()`
- 所有指标调用需包 `try/except`，避免影响主流程

### 5.2 Celery

- `BaseTask.on_success`：`celery_tasks_total.labels(task_name=..., status="success").inc()`
- `BaseTask.on_failure`：`celery_tasks_total.labels(..., status="failure").inc()`

### 5.3 Socket.IO

- `on_connect`（认证成功后）：`active_websockets.labels(namespace="admin"|"tenant"|"user").inc()`
- `on_disconnect`（有 session 时）：`active_websockets.labels(...).dec()`

### 5.4 采样 Gauge

- `celery_queue_length`、`db_pool_size`、`active_tenants` 由 lifespan 后台任务每 15s 调用 `MonitoringService.get_metrics_summary()`，再通过 `update_sampled_gauges()` 写入。

---

## 六、Docker 部署

`docker-compose.dev.yml` 包含：

- **prometheus**：抓取 `host.docker.internal:8000/metrics`
- **grafana**：自动配置 Prometheus 数据源 + 预置 Dashboard

预置 Dashboard 位于 `deploy/grafana/dashboards/`：
- Overview：请求 QPS、延迟、错误率、WebSocket
- AI Gateway：AI 调用量、Token、延迟、成功率
- Infrastructure：Celery 队列、任务率、DB 连接池、WebSocket 分布

---

## 七、前端页面

- 路径：`/admin/system-maintenance/monitoring`
- 组件：`views/admin/system/monitoring/index.vue`
- Tab：实时概览（5s 轮询 metrics-summary）、Grafana 嵌入、告警规则占位
- i18n：`admin.system.monitoring.*`

---

## 八、权限

- 资源：`system_monitoring`
- 父资源：`system_maintenance`
- 操作：`action.system_monitoring.metrics`、`metrics_summary`、`grafana_config`
