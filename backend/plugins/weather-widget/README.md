# Weather Widget Plugin

Header navigation weather widget — a full-featured NovusAI plugin example.

## Features

- **Real-time Weather** — Temperature, apparent temperature, weather condition, humidity, wind speed, UV index
- **24h Hourly Forecast** — Horizontal scrollable hourly temperature + weather icons
- **3-Day Forecast** — Daily high/low with dynamic temperature-mapped color bars
- **Air Quality (AQI)** — US AQI, PM2.5, PM10 via Open-Meteo Air Quality API
- **Auto Location** — Browser Geolocation API + Nominatim reverse geocoding with multi-level fallback
- **City Search** — Debounced search via Open-Meteo Geocoding, supports Chinese and English
- **Local Storage** — City preference and last successful weather data cached in localStorage
- **Skeleton Loading** — Shimmer skeleton screen on first load
- **Windows 11 Fluent Design UI** — Acrylic material, dynamic weather gradients, noise texture, scene decorations
- **AI Skill Pack** — `get_current_weather` + `get_weather_forecast` tools for agent invocation

## API

Based on [Open-Meteo](https://open-meteo.com/) — completely free, no API key required.

- Weather data: `api.open-meteo.com/v1/forecast`
- Air quality: `air-quality-api.open-meteo.com/v1/air-quality`
- Geocoding: `geocoding-api.open-meteo.com/v1/search`
- Reverse geocoding: `nominatim.openstreetmap.org/reverse`

## Extensions

| Type | Name | Description |
|------|------|-------------|
| Skill | `weather-realtime` | 2 tools: current weather + multi-day forecast |
| API | 6 tenant_routes + 6 admin_routes | config / current / forecast / hourly / air-quality / geocoding |
| Frontend | `weather-widget` (header_widget) | Header navigation weather popover |

## API Routes

All routes are registered under both tenant and admin scopes.

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `config` | `get_config` | Plugin configuration |
| GET | `current` | `get_current_weather` | Current weather data |
| GET | `forecast` | `get_forecast` | Multi-day forecast |
| GET | `hourly` | `get_hourly` | 24-hour hourly forecast |
| GET | `air-quality` | `get_air_quality` | Air quality (AQI) |
| GET | `geocoding` | `search_city` | City search |

## Directory Structure

```
weather-widget/
├── plugin.yaml
├── README.md
├── README.zh-CN.md
├── backend/
│   ├── main.py                  # WeatherWidgetPlugin entry
│   ├── open_meteo.py            # Open-Meteo + Nominatim API client (with cache & rate-limit)
│   ├── _loader.py               # Plugin loader
│   ├── skills/
│   │   └── weather_resolver.py  # Skill resolver (2 tools)
│   ├── executors/
│   │   └── weather_widget_executor.py  # Tool executor
│   ├── api/
│   │   └── handlers.py          # 6 API route handlers
│   └── tests/
│       ├── test_open_meteo.py
│       ├── test_skill.py
│       └── test_api_handlers.py
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── index.ts             # Frontend entry
│       ├── WeatherHeaderWidget.vue  # Main widget component
│       ├── use-weather.ts       # Composable (state, API calls, localStorage)
│       ├── styles.ts            # Injected CSS (Fluent Design)
│       ├── locales.ts           # i18n messages (zh-CN / en)
│       ├── weather-codes.ts     # WMO code → icon/scene mapping
│       └── types.ts             # TypeScript type definitions
└── locales/
    ├── zh-CN.json
    └── en.json
```

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_city` | string | Shanghai | Default city on startup |
| `temperature_unit` | enum | celsius | Temperature unit (celsius / fahrenheit) |
| `forecast_days` | integer | 3 | Forecast days (1–7) |
| `cache_ttl` | integer | 600 | Cache TTL in seconds |
| `auto_refresh` | boolean | true | Auto-refresh weather data periodically |

## Testing

```bash
cd backend
python -m pytest plugins/weather-widget/backend/tests/ -v
```
