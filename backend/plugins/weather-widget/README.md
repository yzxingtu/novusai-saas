# Weather Widget Plugin

顶部导航天气组件 — NovusAI 插件系统完整示例。

## 功能

- **实时天气**：温度、天气状况、湿度、风速、UV 指数
- **3 日预报**：每日最高/最低温度 + 天气图标
- **天气动画**：6 种 CSS 动画（晴/多云/雨/雪/雷暴/雾），支持昼夜切换
- **城市搜索**：防抖搜索 + Open-Meteo Geocoding，支持中英文
- **本地存储**：城市偏好保存在浏览器 localStorage，最近 5 个城市快速切换
- **AI 技能包**：`get_current_weather` + `get_weather_forecast`，供智能体调用

## API

基于 [Open-Meteo](https://open-meteo.com/)，完全免费，无需 API Key。

## 扩展点

| 类型 | 名称 | 说明 |
|------|------|------|
| Skill | `weather_widget` | 2 个工具：当前天气 + 多日预报 |
| API | 3 个 tenant_routes | current / forecast / geocoding |
| Frontend | header_widget | 顶部导航天气组件 |

## 目录结构

```
weather-widget/
├── plugin.yaml
├── README.md
├── backend/
│   ├── main.py                  # WeatherWidgetPlugin
│   ├── open_meteo.py            # Open-Meteo API 客户端（含缓存）
│   ├── skills/
│   │   └── weather_resolver.py  # Skill Resolver (2 tools)
│   ├── executors/
│   │   └── weather_widget_executor.py  # Tool Executor
│   ├── api/
│   │   └── handlers.py          # 3 个 API 代理路由
│   └── tests/
│       ├── test_open_meteo.py   # 21 tests
│       ├── test_skill.py        # 20 tests
│       └── test_api_handlers.py # 19 tests
└── locales/
    ├── zh-CN.json
    └── en.json
```

## 测试

```bash
cd backend
python -m pytest plugins/weather-widget/backend/tests/ -v
# 60 tests passed
```
