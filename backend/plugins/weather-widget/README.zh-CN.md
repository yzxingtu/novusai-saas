# 天气组件插件

顶部导航天气组件 — NovusAI 插件系统完整示例。

## 功能

- **实时天气** — 温度、体感温度、天气状况、湿度、风速、UV 指数
- **24 小时逐时预报** — 横向滚动小时温度 + 天气图标
- **3 日预报** — 每日最高/最低温度 + 动态温度色彩映射条
- **空气质量 (AQI)** — 当前免 Key 方案不提供 AQI 时优雅降级为 `--`
- **自动定位** — 浏览器 Geolocation API + Nominatim 反向地理编码
- **城市搜索** — 防抖搜索 + Nominatim，支持中英文
- **本地存储** — 城市偏好和上次成功天气数据缓存在 localStorage
- **骨架屏加载** — 首次加载时显示微光脉冲骨架屏
- **Windows 11 Fluent Design UI** — 亚克力材质、动态天气渐变、噪点纹理、场景装饰
- **AI 技能包** — `get_current_weather` + `get_weather_forecast`，供智能体调用

## API

基于免 Key 的 [MET Norway](https://api.met.no/weatherapi/locationforecast/2.0/documentation) 和 [Nominatim](https://operations.osmfoundation.org/policies/nominatim/)。

- 天气数据：`api.met.no/weatherapi/locationforecast/2.0/compact`
- 地理编码和反查：`nominatim.openstreetmap.org/search|reverse`
- 后端鉴权：不需要

## 扩展点

| 类型 | 名称 | 说明 |
|------|------|------|
| Skill | `weather-realtime` | 2 个工具：当前天气 + 多日预报 |
| API | 6 个 tenant_routes + 6 个 admin_routes | config / current / forecast / hourly / air-quality / geocoding |
| Frontend | `weather-widget` (header_widget) | 顶部导航天气弹窗组件 |

## API 路由

所有路由同时注册在 tenant 和 admin 两个作用域下。

| 方法 | 路径 | Handler | 说明 |
|------|------|---------|------|
| GET | `config` | `get_config` | 插件配置 |
| GET | `current` | `get_current_weather` | 当前天气数据 |
| GET | `forecast` | `get_forecast` | 多日预报 |
| GET | `hourly` | `get_hourly` | 24 小时逐时预报 |
| GET | `air-quality` | `get_air_quality` | 空气质量 (AQI) |
| GET | `geocoding` | `search_city` | 城市搜索 |

## 目录结构

```
weather-widget/
├── plugin.yaml
├── README.md
├── README.zh-CN.md
├── backend/
│   ├── main.py                  # WeatherWidgetPlugin 入口
│   ├── open_meteo.py            # Open-Meteo + Nominatim API 客户端（含缓存和限速）
│   ├── _loader.py               # 插件加载器
│   ├── skills/
│   │   └── weather_resolver.py  # Skill 解析器（2 个工具）
│   ├── executors/
│   │   └── weather_widget_executor.py  # 工具执行器
│   ├── api/
│   │   └── handlers.py          # 6 个 API 路由处理器
│   └── tests/
│       ├── test_open_meteo.py
│       ├── test_skill.py
│       └── test_api_handlers.py
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── index.ts             # 前端入口
│       ├── WeatherHeaderWidget.vue  # 主组件
│       ├── use-weather.ts       # Composable（状态、API 调用、localStorage）
│       ├── styles.ts            # 注入式 CSS（Fluent Design）
│       ├── locales.ts           # 国际化文案（中/英）
│       ├── weather-codes.ts     # WMO 天气代码 → 图标/场景映射
│       └── types.ts             # TypeScript 类型定义
└── locales/
    ├── zh-CN.json
    └── en.json
```

## 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `default_city` | string | Shanghai | 默认城市 |
| `temperature_unit` | enum | celsius | 温度单位（celsius / fahrenheit） |
| `forecast_days` | integer | 3 | 预报天数（1–7） |
| `cache_ttl` | integer | 600 | 缓存时间（秒） |
| `auto_refresh` | boolean | true | 是否自动刷新天气数据 |

## 测试

```bash
cd backend
python -m pytest plugins/weather-widget/backend/tests/ -v
```
