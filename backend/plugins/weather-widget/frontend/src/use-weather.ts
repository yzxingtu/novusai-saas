/**
 * Shared weather state for plugin widgets.
 *
 * Header and dashboard widgets use the same singleton store, so
 * data loading, refresh cadence, stale state, and city selection stay in sync.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { buildPluginApiBase, requestClient } from '@novus/plugin-shared';

export type TemperatureUnit = 'celsius' | 'fahrenheit';

export interface WeatherCurrent {
  temperature: number | null;
  apparent_temperature: number | null;
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
  sunrise: string | null;
  sunset: string | null;
}

export interface WeatherHourly {
  time: string;
  temperature: number | null;
  weather_code: number;
  weather_icon: string;
  weather_text_zh: string;
  weather_text_en: string;
  is_current?: boolean;
}

export interface AirQuality {
  aqi: number | null;
  pm2_5: number | null;
  pm10: number | null;
  european_aqi: number | null;
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
  temperature_unit?: TemperatureUnit;
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

interface CachedWeatherData {
  current: WeatherCurrent | null;
  forecast: WeatherForecastDay[];
  hourly: WeatherHourly[];
  airQuality: AirQuality | null;
  timestamp: number;
}

interface WeatherStore {
  cityName: ReturnType<typeof computed<string>>;
  recentCities: ReturnType<typeof computed<CityInfo[]>>;
  current: typeof currentRef;
  forecast: typeof forecastRef;
  hourly: typeof hourlyRef;
  airQuality: typeof airQualityRef;
  loading: typeof loadingRef;
  initialLoading: typeof initialLoadingRef;
  error: typeof errorRef;
  locating: typeof locatingRef;
  locateError: typeof locateErrorRef;
  showCitySelector: typeof showCitySelectorRef;
  isStale: typeof isStaleRef;
  pluginConfig: typeof pluginConfigRef;
  temperatureUnit: ReturnType<typeof computed<TemperatureUnit>>;
  forecastDays: ReturnType<typeof computed<number>>;
  lastUpdatedAt: typeof lastUpdatedAtRef;
  fetchAll: () => Promise<void>;
  searchCity: (name: string) => Promise<CityInfo[]>;
  selectCity: (city: CityInfo) => Promise<void>;
  geolocate: () => Promise<void>;
  mount: () => Promise<void>;
  unmount: () => void;
}

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
  { name: '苏州', latitude: 31.299, longitude: 120.5853, country: 'China' },
  { name: '天津', latitude: 39.3434, longitude: 117.3616, country: 'China' },
];

const STORAGE_KEY = 'novusai_weather_config';
const WEATHER_DATA_KEY = 'novusai_weather_data';
const MAX_RECENT_CITIES = 6;
const DEFAULT_CACHE_TTL_SECONDS = 600;
const WEATHER_PLUGIN_NAME = 'weather-widget';
const WEATHER_PLUGIN_REQUEST_OPTIONS = {
  showCodeMessage: false,
  showErrorMessage: false,
  skipAuthRecovery: true,
};

const DEFAULT_LOCAL: WeatherLocalConfig = {
  city: 'Shanghai',
  latitude: 31.2304,
  longitude: 121.4737,
  recentCities: [
    { name: 'Shanghai', latitude: 31.2304, longitude: 121.4737, country: 'China' },
  ],
};

const localConfigExistsRef = ref(false);

function clamp(num: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, num));
}

function resolveLegacyPathApiBase(): string | null {
  const path = window.location.pathname;
  if (path.startsWith('/admin')) {
    return `/admin/plugins/${WEATHER_PLUGIN_NAME}/api`;
  }
  if (path.startsWith('/tenant')) {
    return `/tenant/plugins/${WEATHER_PLUGIN_NAME}/api`;
  }
  return null;
}

export function resolveWeatherApiBase(): string {
  if (typeof buildPluginApiBase === 'function') {
    try {
      return buildPluginApiBase(WEATHER_PLUGIN_NAME);
    } catch {
      // Fall through to the legacy explicit-path fallback below.
    }
  }

  const legacyApiBase = resolveLegacyPathApiBase();
  if (legacyApiBase) {
    return legacyApiBase;
  }

  throw new Error('Weather plugin host endpoint is unavailable');
}

function normalizeTemperatureUnit(unit: unknown): TemperatureUnit {
  return unit === 'fahrenheit' ? 'fahrenheit' : 'celsius';
}

function loadLocalConfig(): WeatherLocalConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    localConfigExistsRef.value = Boolean(raw);
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
  } catch {
    localConfigExistsRef.value = false;
  }
  return { ...DEFAULT_LOCAL, recentCities: [...DEFAULT_LOCAL.recentCities] };
}

function saveLocalConfig(cfg: WeatherLocalConfig): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
    localConfigExistsRef.value = true;
  } catch {
    /* noop */
  }
}

function loadCachedWeather(): CachedWeatherData | null {
  try {
    const raw = localStorage.getItem(WEATHER_DATA_KEY);
    if (raw) {
      return JSON.parse(raw) as CachedWeatherData;
    }
  } catch {
    /* noop */
  }
  return null;
}

function saveCachedWeather(data: CachedWeatherData): void {
  try {
    localStorage.setItem(WEATHER_DATA_KEY, JSON.stringify(data));
  } catch {
    /* noop */
  }
}

const localConfigRef = ref<WeatherLocalConfig>(loadLocalConfig());
const pluginConfigRef = ref<PluginConfig>({});
const currentRef = ref<WeatherCurrent | null>(null);
const forecastRef = ref<WeatherForecastDay[]>([]);
const hourlyRef = ref<WeatherHourly[]>([]);
const airQualityRef = ref<AirQuality | null>(null);
const loadingRef = ref(false);
const initialLoadingRef = ref(true);
const errorRef = ref<string | null>(null);
const locatingRef = ref(false);
const locateErrorRef = ref<string | null>(null);
const showCitySelectorRef = ref(false);
const isStaleRef = ref(false);
const lastUpdatedAtRef = ref<number | null>(null);

let sharedStore: WeatherStore | null = null;
let consumerCount = 0;
let initialized = false;
let requestSeq = 0;
let refreshTimer: ReturnType<typeof setInterval> | null = null;
let abortController: AbortController | null = null;

function markStaleByTimestamp(ts: number | null, staleThresholdMs: number): void {
  if (!ts) {
    isStaleRef.value = false;
    return;
  }
  isStaleRef.value = Date.now() - ts > staleThresholdMs;
}

function syncRefreshTimer(intervalMs: number, autoRefresh: boolean, fetchAll: () => Promise<void>): void {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
  if (!autoRefresh || consumerCount <= 0) {
    return;
  }
  refreshTimer = setInterval(() => {
    void fetchAll();
  }, intervalMs);
}

function createStore(): WeatherStore {
  const cityName = computed(() => localConfigRef.value.city);
  const recentCities = computed(() => localConfigRef.value.recentCities);
  const temperatureUnit = computed(() =>
    normalizeTemperatureUnit(pluginConfigRef.value.temperature_unit),
  );
  const forecastDays = computed(() =>
    clamp(pluginConfigRef.value.forecast_days ?? 3, 1, 7),
  );
  const refreshIntervalMs = computed(() =>
    clamp(pluginConfigRef.value.cache_ttl ?? DEFAULT_CACHE_TTL_SECONDS, 60, 3600) * 1000,
  );
  const staleThresholdMs = computed(() => Math.max(refreshIntervalMs.value, 5 * 60 * 1000));

  async function fetchPluginConfig(): Promise<void> {
    try {
      const resp = await requestClient.get<{ config: PluginConfig }>(
        `${resolveWeatherApiBase()}/config`,
        WEATHER_PLUGIN_REQUEST_OPTIONS,
      );
      if (resp?.config) {
        pluginConfigRef.value = resp.config;
      }
    } catch {
      pluginConfigRef.value = {};
    }
  }

  async function resolveDefaultCityFromConfig(): Promise<void> {
    const defaultCityName = pluginConfigRef.value.default_city?.trim();
    if (!defaultCityName || localConfigExistsRef.value) {
      return;
    }
    const cities = await searchCity(defaultCityName);
    if (cities.length > 0) {
      const primary = cities[0]!;
      localConfigRef.value.city = primary.name;
      localConfigRef.value.latitude = primary.latitude;
      localConfigRef.value.longitude = primary.longitude;
      localConfigRef.value.recentCities = [primary];
      saveLocalConfig(localConfigRef.value);
      return;
    }
    localConfigRef.value.city = defaultCityName;
    saveLocalConfig(localConfigRef.value);
  }

  async function fetchAll(): Promise<void> {
    const seq = ++requestSeq;
    if (abortController) {
      abortController.abort();
    }
    abortController = new AbortController();
    loadingRef.value = true;
    errorRef.value = null;

    const { latitude, longitude } = localConfigRef.value;
    const days = forecastDays.value;

    try {
      const [weatherResp, forecastResp, hourlyResp, aqiResp] = await Promise.all([
        requestClient.get<{ weather: WeatherCurrent }>(
          `${resolveWeatherApiBase()}/current`,
          {
            ...WEATHER_PLUGIN_REQUEST_OPTIONS,
            params: { lat: latitude, lon: longitude },
            signal: abortController.signal,
          },
        ),
        requestClient
          .get<{ forecast: WeatherForecastDay[] }>(
            `${resolveWeatherApiBase()}/forecast`,
            {
              ...WEATHER_PLUGIN_REQUEST_OPTIONS,
              params: { lat: latitude, lon: longitude, days },
              signal: abortController.signal,
            },
          )
          .catch(() => null),
        requestClient
          .get<{ hourly: WeatherHourly[] }>(
            `${resolveWeatherApiBase()}/hourly`,
            {
              ...WEATHER_PLUGIN_REQUEST_OPTIONS,
              params: { lat: latitude, lon: longitude },
              signal: abortController.signal,
            },
          )
          .catch(() => null),
        requestClient
          .get<{ air_quality: AirQuality }>(
            `${resolveWeatherApiBase()}/air-quality`,
            {
              ...WEATHER_PLUGIN_REQUEST_OPTIONS,
              params: { lat: latitude, lon: longitude },
              signal: abortController.signal,
            },
          )
          .catch(() => null),
      ]);

      if (seq !== requestSeq) {
        return;
      }

      currentRef.value = weatherResp?.weather ?? null;
      forecastRef.value = (forecastResp?.forecast ?? []).slice(0, days);
      hourlyRef.value = hourlyResp?.hourly ?? [];
      airQualityRef.value = aqiResp?.air_quality ?? null;
      lastUpdatedAtRef.value = Date.now();
      markStaleByTimestamp(lastUpdatedAtRef.value, staleThresholdMs.value);

      saveCachedWeather({
        current: currentRef.value,
        forecast: forecastRef.value,
        hourly: hourlyRef.value,
        airQuality: airQualityRef.value,
        timestamp: lastUpdatedAtRef.value,
      });
    } catch (err: unknown) {
      if (seq !== requestSeq) {
        return;
      }
      const message = err instanceof Error ? err.message : String(err);
      if (message.toLowerCase().includes('aborted')) {
        return;
      }
      errorRef.value = message;
      const cached = loadCachedWeather();
      if (cached?.current) {
        currentRef.value = cached.current;
        forecastRef.value = cached.forecast.slice(0, days);
        hourlyRef.value = cached.hourly;
        airQualityRef.value = cached.airQuality;
        lastUpdatedAtRef.value = cached.timestamp;
        markStaleByTimestamp(cached.timestamp, staleThresholdMs.value);
      }
    } finally {
      if (seq === requestSeq) {
        loadingRef.value = false;
        initialLoadingRef.value = false;
      }
    }
  }

  async function searchCity(name: string): Promise<CityInfo[]> {
    const query = name.trim();
    if (!query) {
      return [];
    }
    try {
      const resp = await requestClient.get<{ cities: CityInfo[] }>(
        `${resolveWeatherApiBase()}/geocoding`,
        {
          ...WEATHER_PLUGIN_REQUEST_OPTIONS,
          params: { name: query, count: 8 },
        },
      );
      return resp?.cities ?? [];
    } catch {
      return [];
    }
  }

  async function selectCity(city: CityInfo): Promise<void> {
    localConfigRef.value.city = city.name;
    localConfigRef.value.latitude = city.latitude;
    localConfigRef.value.longitude = city.longitude;
    const nextRecent = localConfigRef.value.recentCities.filter(
      (item) =>
        !(
          Math.abs(item.latitude - city.latitude) < 0.01 &&
          Math.abs(item.longitude - city.longitude) < 0.01
        ),
    );
    nextRecent.unshift(city);
    localConfigRef.value.recentCities = nextRecent.slice(0, MAX_RECENT_CITIES);
    saveLocalConfig(localConfigRef.value);
    showCitySelectorRef.value = false;
    await fetchAll();
  }

  async function useTransientCoordinates(city: CityInfo): Promise<void> {
    localConfigRef.value.city = city.name;
    localConfigRef.value.latitude = city.latitude;
    localConfigRef.value.longitude = city.longitude;
    showCitySelectorRef.value = false;
    await fetchAll();
  }

  async function geolocate(): Promise<void> {
    if (!navigator.geolocation) {
      locateErrorRef.value = 'locate_failed';
      return;
    }
    locatingRef.value = true;
    locateErrorRef.value = null;
    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 300000,
        });
      });
      const { latitude, longitude } = pos.coords;
      let resolvedCity: CityInfo | null = null;
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          const resp = await requestClient.get<{ cities: CityInfo[] }>(
            `${resolveWeatherApiBase()}/geocoding`,
            {
              ...WEATHER_PLUGIN_REQUEST_OPTIONS,
              params: { lat: latitude, lon: longitude },
            },
          );
          if (resp?.cities?.length && resp.cities[0]?.name) {
            resolvedCity = resp.cities[0];
            break;
          }
        } catch {
          /* retry once */
        }
        if (attempt === 0) {
          await new Promise((resolve) => setTimeout(resolve, 500));
        }
      }
      if (resolvedCity) {
        await useTransientCoordinates(resolvedCity);
      } else {
        await useTransientCoordinates({
          name: `${latitude.toFixed(2)}, ${longitude.toFixed(2)}`,
          latitude,
          longitude,
        });
        locateErrorRef.value = 'locate_fallback';
      }
    } catch {
      locateErrorRef.value = 'locate_failed';
    } finally {
      locatingRef.value = false;
    }
  }

  async function mount(): Promise<void> {
    consumerCount += 1;
    if (!initialized) {
      initialized = true;
      const cached = loadCachedWeather();
      if (cached?.current) {
        currentRef.value = cached.current;
        forecastRef.value = cached.forecast;
        hourlyRef.value = cached.hourly;
        airQualityRef.value = cached.airQuality;
        lastUpdatedAtRef.value = cached.timestamp;
        initialLoadingRef.value = false;
      }
      await fetchPluginConfig();
      await resolveDefaultCityFromConfig();
      await fetchAll();
    }
    syncRefreshTimer(
      refreshIntervalMs.value,
      pluginConfigRef.value.auto_refresh ?? true,
      fetchAll,
    );
  }

  function unmount(): void {
    consumerCount = Math.max(0, consumerCount - 1);
    if (consumerCount <= 0 && refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  return {
    cityName,
    recentCities,
    current: currentRef,
    forecast: forecastRef,
    hourly: hourlyRef,
    airQuality: airQualityRef,
    loading: loadingRef,
    initialLoading: initialLoadingRef,
    error: errorRef,
    locating: locatingRef,
    locateError: locateErrorRef,
    showCitySelector: showCitySelectorRef,
    isStale: isStaleRef,
    pluginConfig: pluginConfigRef,
    temperatureUnit,
    forecastDays,
    lastUpdatedAt: lastUpdatedAtRef,
    fetchAll,
    searchCity,
    selectCity,
    geolocate,
    mount,
    unmount,
  };
}

export function useWeather() {
  if (!sharedStore) {
    sharedStore = createStore();
  }
  onMounted(() => {
    void sharedStore?.mount();
  });
  onBeforeUnmount(() => {
    sharedStore?.unmount();
  });
  return sharedStore;
}
