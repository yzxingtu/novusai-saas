/**
 * 天气数据 Composable
 *
 * 管理天气数据获取、localStorage 持久化、自动刷新、浏览器定位。
 * 所有可配置项从后端插件配置 API 读取（default_city, forecast_days, cache_ttl, auto_refresh）。
 */

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { requestClient } from '@novus/plugin-shared';

// ── 类型 ──

export interface WeatherCurrent {
  temperature: number | null;
  weather_code: number;
  weather_icon: string;
  weather_text_zh: string;
  weather_text_en: string;
  humidity: number | null;
  wind_speed: number | null;
  uv_index: number | null;
  is_day: boolean;
}

export interface WeatherForecastDay {
  date: string;
  temp_max: number | null;
  temp_min: number | null;
  weather_code: number;
  weather_icon: string;
  weather_text_zh: string;
  weather_text_en: string;
}

export interface CityInfo {
  name: string;
  country?: string;
  admin1?: string;
  latitude: number;
  longitude: number;
}

interface PluginConfig {
  default_city?: string;
  temperature_unit?: string;
  forecast_days?: number;
  cache_ttl?: number;
  auto_refresh?: boolean;
}

interface WeatherLocalConfig {
  city: string;
  latitude: number;
  longitude: number;
  recentCities: CityInfo[];
}

// ── 热门城市 ──

export const POPULAR_CITIES: CityInfo[] = [
  { name: '北京', latitude: 39.9042, longitude: 116.4074, country: 'China' },
  { name: '上海', latitude: 31.2304, longitude: 121.4737, country: 'China' },
  { name: '广州', latitude: 23.1291, longitude: 113.2644, country: 'China' },
  { name: '深圳', latitude: 22.5431, longitude: 114.0579, country: 'China' },
  { name: '杭州', latitude: 30.2741, longitude: 120.1551, country: 'China' },
  { name: '成都', latitude: 30.5728, longitude: 104.0668, country: 'China' },
  { name: '武汉', latitude: 30.5928, longitude: 114.3055, country: 'China' },
  { name: '南京', latitude: 32.0603, longitude: 118.7969, country: 'China' },
  { name: '重庆', latitude: 29.4316, longitude: 106.9123, country: 'China' },
  { name: '西安', latitude: 34.3416, longitude: 108.9398, country: 'China' },
  { name: '苏州', latitude: 31.2990, longitude: 120.5853, country: 'China' },
  { name: '天津', latitude: 39.3434, longitude: 117.3616, country: 'China' },
];

// ── 常量 ──

const STORAGE_KEY = 'novusai_weather_config';
const MAX_RECENT_CITIES = 5;

const DEFAULT_LOCAL: WeatherLocalConfig = {
  city: '上海',
  latitude: 31.2304,
  longitude: 121.4737,
  recentCities: [
    { name: '上海', latitude: 31.2304, longitude: 121.4737, country: 'China' },
  ],
};

function loadLocalConfig(): WeatherLocalConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<WeatherLocalConfig>;
      return {
        city: parsed.city || DEFAULT_LOCAL.city,
        latitude: parsed.latitude ?? DEFAULT_LOCAL.latitude,
        longitude: parsed.longitude ?? DEFAULT_LOCAL.longitude,
        recentCities:
          Array.isArray(parsed.recentCities) && parsed.recentCities.length > 0
            ? parsed.recentCities
            : DEFAULT_LOCAL.recentCities,
      };
    }
  } catch { /* ignore */ }
  return { ...DEFAULT_LOCAL, recentCities: [...DEFAULT_LOCAL.recentCities] };
}

function saveLocalConfig(cfg: WeatherLocalConfig): void {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg)); } catch { /* ignore */ }
}

// ── Composable ──

export function useWeather() {
  const router = useRouter();
  const localConfig = ref<WeatherLocalConfig>(loadLocalConfig());
  const pluginConfig = ref<PluginConfig>({});
  const current = ref<WeatherCurrent | null>(null);
  const forecast = ref<WeatherForecastDay[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const locating = ref(false);
  const showCitySelector = ref(false);

  let refreshTimer: ReturnType<typeof setInterval> | null = null;

  const cityName = computed(() => localConfig.value.city);
  const recentCities = computed(() => localConfig.value.recentCities);

  const apiBase = computed(() => {
    const path = router.currentRoute.value.path;
    const prefix = path.startsWith('/admin') ? '/admin' : '/tenant';
    return `${prefix}/plugins/weather-widget/api`;
  });

  // ── 从后端获取插件配置 ──

  async function fetchPluginConfig(): Promise<void> {
    try {
      const resp = await requestClient.get<{ config: PluginConfig }>(
        `${apiBase.value}/config`,
      );
      if (resp?.config) {
        pluginConfig.value = resp.config;
      }
    } catch { /* use defaults */ }
  }

  // ── API ──

  async function fetchCurrentWeather(): Promise<void> {
    try {
      const resp = await requestClient.get<{ weather: WeatherCurrent }>(
        `${apiBase.value}/current`,
        { params: { lat: localConfig.value.latitude, lon: localConfig.value.longitude } },
      );
      if (resp?.weather) { current.value = resp.weather; error.value = null; }
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : String(err);
    }
  }

  async function fetchForecast(): Promise<void> {
    try {
      const resp = await requestClient.get<{ forecast: WeatherForecastDay[] }>(
        `${apiBase.value}/forecast`,
        { params: { lat: localConfig.value.latitude, lon: localConfig.value.longitude } },
      );
      if (resp?.forecast) { forecast.value = resp.forecast; }
    } catch { /* ignore */ }
  }

  async function fetchAll(): Promise<void> {
    loading.value = true;
    error.value = null;
    try { await Promise.all([fetchCurrentWeather(), fetchForecast()]); }
    finally { loading.value = false; }
  }

  async function searchCity(name: string): Promise<CityInfo[]> {
    try {
      const resp = await requestClient.get<{ cities: CityInfo[] }>(
        `${apiBase.value}/geocoding`, { params: { name, count: 8 } },
      );
      return resp?.cities ?? [];
    } catch { return []; }
  }

  // ── 定位 ──

  async function geolocate(): Promise<void> {
    if (!navigator.geolocation) return;
    locating.value = true;
    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          timeout: 10000, maximumAge: 300000,
        });
      });
      const { latitude, longitude } = pos.coords;
      const city: CityInfo = { name: `${latitude.toFixed(2)}, ${longitude.toFixed(2)}`, latitude, longitude };
      try {
        const resp = await requestClient.get<{ cities: CityInfo[] }>(
          `${apiBase.value}/geocoding`,
          { params: { lat: latitude, lon: longitude } },
        );
        if (resp?.cities?.length) {
          city.name = resp.cities[0]!.name;
        }
      } catch { /* use coordinate name as fallback */ }
      selectCity(city);
    } catch { /* ignore geolocation errors */ }
    finally { locating.value = false; }
  }

  // ── 城市切换 ──

  function selectCity(city: CityInfo): void {
    localConfig.value.city = city.name;
    localConfig.value.latitude = city.latitude;
    localConfig.value.longitude = city.longitude;
    const recent = localConfig.value.recentCities.filter(
      (c: CityInfo) => !(Math.abs(c.latitude - city.latitude) < 0.01 && Math.abs(c.longitude - city.longitude) < 0.01),
    );
    recent.unshift(city);
    localConfig.value.recentCities = recent.slice(0, MAX_RECENT_CITIES);
    saveLocalConfig(localConfig.value);
    showCitySelector.value = false;
    fetchAll();
  }

  // ── 生命周期 ──

  onMounted(async () => {
    await fetchPluginConfig();

    const refreshInterval = (pluginConfig.value.cache_ttl ?? 600) * 1000;
    const autoRefresh = pluginConfig.value.auto_refresh ?? true;

    await fetchAll();

    if (autoRefresh) {
      refreshTimer = setInterval(fetchAll, refreshInterval);
    }
  });

  onBeforeUnmount(() => { if (refreshTimer) clearInterval(refreshTimer); });
  watch(() => localConfig.value.city, () => saveLocalConfig(localConfig.value));

  return {
    cityName, recentCities, current, forecast, loading, error,
    locating, showCitySelector, pluginConfig, fetchAll, searchCity, selectCity, geolocate,
  };
}
