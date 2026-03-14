<script lang="ts" setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { Popover, Tooltip } from 'ant-design-vue';
import { IconifyIcon, $t } from '@novus/plugin-shared';

import type { CityInfo } from './use-weather';
import { useWeather, POPULAR_CITIES } from './use-weather';
import { getWeatherCodeInfo, getWeatherBg } from './weather-codes';

const {
  cityName, recentCities, current, forecast, hourly, airQuality,
  loading, initialLoading, error, locating, locateError,
  showCitySelector, isStale,
  fetchAll, searchCity, selectCity, geolocate,
} = useWeather();

const isZh = computed(() => $t('plugin.weather-widget._meta.lang') === 'zh');

function weatherText(item: { weather_text_zh?: string; weather_text_en?: string }): string {
  return isZh.value ? (item.weather_text_zh || item.weather_text_en || '') : (item.weather_text_en || item.weather_text_zh || '');
}

const popoverOpen = ref(false);
const searchKeyword = ref('');
const searchResults = ref<CityInfo[]>([]);
const searching = ref(false);
let searchTimer: ReturnType<typeof setTimeout> | null = null;

function handleSearchInput(val: string) {
  searchKeyword.value = val;
  if (searchTimer) clearTimeout(searchTimer);
  if (!val.trim()) { searchResults.value = []; searching.value = false; return; }
  searching.value = true;
  searchTimer = setTimeout(async () => {
    searchResults.value = await searchCity(val.trim());
    searching.value = false;
  }, 400);
}

function handleSelectCity(city: CityInfo) {
  selectCity(city);
  searchKeyword.value = '';
  searchResults.value = [];
}

function getIcon(code: number, isDay = true): string {
  return getWeatherCodeInfo(code, isDay).icon;
}

function getBg(code: number, isDay = true) {
  return getWeatherBg(code, isDay);
}

function formatDate(dateStr: string, index: number): string {
  if (index === 0) return $t('plugin.weather-widget.ui.today');
  if (index === 1) return $t('plugin.weather-widget.ui.tomorrow');
  if (index === 2) return $t('plugin.weather-widget.ui.day_after');
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function formatWeekday(dateStr: string): string {
  const dayIndex = new Date(dateStr).getDay();
  return $t(`plugin.weather-widget.ui.weekday_${dayIndex}`);
}

function formatTime(timeStr: string, isCurrent: boolean | undefined): string {
  if (isCurrent) return $t('plugin.weather-widget.ui.now');
  return timeStr;
}

function formatSunTime(isoStr: string | null | undefined): string {
  if (!isoStr) return '--:--';
  const t = isoStr.includes('T') ? isoStr.split('T')[1] : isoStr;
  return t ? t.substring(0, 5) : '--:--';
}

function aqiLevel(aqi: number | null | undefined): string {
  if (aqi == null) return '--';
  if (aqi <= 50) return $t('plugin.weather-widget.aqi_level.good');
  if (aqi <= 100) return $t('plugin.weather-widget.aqi_level.moderate');
  if (aqi <= 150) return $t('plugin.weather-widget.aqi_level.unhealthy_sensitive');
  if (aqi <= 200) return $t('plugin.weather-widget.aqi_level.unhealthy');
  if (aqi <= 300) return $t('plugin.weather-widget.aqi_level.very_unhealthy');
  return $t('plugin.weather-widget.aqi_level.hazardous');
}

function aqiColor(aqi: number | null | undefined): string {
  if (aqi == null) return 'rgba(255,255,255,0.5)';
  if (aqi <= 50) return '#4ade80';
  if (aqi <= 100) return '#facc15';
  if (aqi <= 150) return '#fb923c';
  if (aqi <= 200) return '#f87171';
  if (aqi <= 300) return '#a78bfa';
  return '#9f1239';
}

const todayForecast = computed(() => forecast.value?.[0] ?? null);

const TEMP_COLOR_STOPS: [number, number, number, number][] = [
  [-10, 108, 180, 238], [0, 147, 197, 253], [10, 167, 216, 160],
  [20, 253, 230, 138], [30, 251, 146, 60], [40, 239, 68, 68],
];

function tempToColor(temp: number): string {
  const t = Math.max(-10, Math.min(40, temp));
  for (let i = 1; i < TEMP_COLOR_STOPS.length; i++) {
    const [t1, r1, g1, b1] = TEMP_COLOR_STOPS[i - 1]!;
    const [t2, r2, g2, b2] = TEMP_COLOR_STOPS[i]!;
    if (t <= t2) {
      const p = (t - t1) / (t2 - t1);
      const r = Math.round(r1 + (r2 - r1) * p);
      const g = Math.round(g1 + (g2 - g1) * p);
      const b = Math.round(b1 + (b2 - b1) * p);
      return `rgb(${r},${g},${b})`;
    }
  }
  return 'rgb(239,68,68)';
}

function tempBarStyle(min: number | null, max: number | null): Record<string, string> {
  if (min === null || max === null || !forecast.value.length) return {};
  const allMin = Math.min(...forecast.value.map(d => d.temp_min ?? 99));
  const allMax = Math.max(...forecast.value.map(d => d.temp_max ?? -99));
  const range = allMax - allMin || 1;
  const left = ((min - allMin) / range) * 100;
  const width = ((max - min) / range) * 100;
  return {
    left: `${left}%`,
    width: `${Math.max(width, 14)}%`,
    background: `linear-gradient(to right, ${tempToColor(min)}, ${tempToColor(max)})`,
  };
}

const bgInfo = computed(() => {
  if (!current.value) return { bgClass: 'wx-bg--cloudy-day', scene: 'cloud' as const };
  return getBg(current.value.weather_code, current.value.is_day);
});

const hourlyScrollRef = ref<HTMLElement | null>(null);

watch(hourly, () => {
  nextTick(() => {
    const el = hourlyScrollRef.value;
    if (!el) return;
    const currentItem = el.querySelector('.wx-hourly-item--current') as HTMLElement | null;
    if (currentItem) {
      el.scrollLeft = currentItem.offsetLeft - 12;
    }
  });
});
</script>

<template>
  <Popover
    v-model:open="popoverOpen"
    trigger="click"
    placement="bottomRight"
    :arrow="false"
    overlay-class-name="weather-popover-immersive"
  >
    <!-- 顶栏触发按钮 -->
    <template #default>
      <Tooltip :title="$t('plugin.weather-widget.ui.temperature')" placement="bottom">
        <div class="flex items-center gap-1 px-2 py-1 rounded-md cursor-pointer transition-colors hover:bg-accent">
          <template v-if="current && !initialLoading">
            <IconifyIcon :icon="`lucide:${getIcon(current.weather_code, current.is_day)}`" class="size-4 text-primary" />
            <span class="text-[13px] font-semibold hidden sm:inline">{{ current.temperature !== null ? `${Math.round(current.temperature)}°` : '--' }}</span>
          </template>
          <template v-else-if="initialLoading">
            <IconifyIcon icon="lucide:loader-2" class="size-4 animate-spin text-muted-foreground" />
          </template>
          <template v-else>
            <IconifyIcon icon="lucide:cloud-off" class="size-4 text-muted-foreground" />
          </template>
        </div>
      </Tooltip>
    </template>

    <!-- 面板 -->
    <template #content>
      <div
        class="relative rounded-2xl overflow-hidden text-white font-sans wx-noise"
        style="width: 340px"
        :class="bgInfo.bgClass"
      >
        <div class="wx-panel-inner-glow" />
        <Transition name="wx-view" mode="out-in">
          <!-- ═══ 城市选择视图 ═══ -->
          <div v-if="showCitySelector" key="city" class="relative z-[2] p-4 flex flex-col gap-3 wx-panel-scroll" style="max-height: 520px">
            <div class="flex justify-between items-center">
              <span class="text-sm font-semibold tracking-wide">{{ $t('plugin.weather-widget.ui.change_city') }}</span>
              <button
                class="flex items-center justify-center size-7 rounded-full bg-white/[0.08] text-inherit cursor-pointer transition-colors hover:bg-white/[0.16] active:scale-95"
                @click="showCitySelector = false"
              >
                <IconifyIcon icon="lucide:x" class="size-3.5" />
              </button>
            </div>

            <!-- 搜索 -->
            <div class="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-white/[0.06] border border-white/[0.06]">
              <IconifyIcon icon="lucide:search" class="size-3.5 opacity-50" />
              <input
                :value="searchKeyword"
                :placeholder="$t('plugin.weather-widget.ui.search_city')"
                class="flex-1 bg-transparent border-none outline-none text-inherit text-[13px] placeholder:text-white/30"
                @input="handleSearchInput(($event.target as HTMLInputElement).value)"
              />
            </div>

            <!-- 搜索结果 -->
            <div v-if="searchKeyword.trim()" class="flex flex-col gap-1 max-h-40 overflow-y-auto">
              <div v-if="searching" class="flex items-center gap-2 py-3 justify-center text-xs opacity-60">
                <IconifyIcon icon="lucide:loader-2" class="size-3.5 animate-spin" /> {{ $t('plugin.weather-widget.ui.loading') }}
              </div>
              <button
                v-for="c in searchResults" :key="`${c.latitude}-${c.longitude}`"
                class="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-white/[0.06] text-inherit cursor-pointer text-[13px] text-left transition-all hover:bg-white/[0.14] active:scale-[0.98] border border-transparent hover:border-white/[0.06]"
                @click="handleSelectCity(c)"
              >
                <IconifyIcon icon="lucide:map-pin" class="size-3.5 opacity-40 shrink-0" />
                <span>{{ c.name }}</span>
                <span v-if="c.admin1" class="opacity-40 text-xs">{{ c.admin1 }}</span>
              </button>
              <div v-if="!searching && searchResults.length === 0" class="flex items-center gap-2 py-3 justify-center text-xs opacity-50">
                {{ $t('plugin.weather-widget.error.city_not_found') }}
              </div>
            </div>

            <!-- 定位 -->
            <button
              class="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-white/[0.06] text-inherit cursor-pointer text-[13px] justify-center font-medium transition-colors hover:bg-white/[0.12] active:scale-[0.98] disabled:opacity-30 border border-white/[0.06]"
              :disabled="locating"
              @click="geolocate"
            >
              <IconifyIcon :icon="locating ? 'lucide:loader-2' : 'lucide:locate'" :class="locating ? 'size-3.5 animate-spin' : 'size-3.5'" />
              {{ locating ? $t('plugin.weather-widget.ui.locating') : $t('plugin.weather-widget.ui.auto_locate') }}
            </button>
            <div v-if="locateError" class="text-xs text-center opacity-50">
              {{ $t(`plugin.weather-widget.error.${locateError}`) }}
            </div>

            <!-- 最近城市 -->
            <div v-if="recentCities.length > 0" class="flex flex-col gap-2">
              <div class="text-[10px] uppercase tracking-wider opacity-40 font-semibold">{{ $t('plugin.weather-widget.ui.recent_cities') }}</div>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="c in recentCities" :key="`r-${c.latitude}`"
                  class="px-3 py-1.5 rounded-full bg-white/[0.06] text-inherit cursor-pointer text-xs transition-colors hover:bg-white/[0.12] active:scale-95 border border-white/[0.06]"
                  @click="handleSelectCity(c)"
                >
                  {{ c.name }}
                </button>
              </div>
            </div>

            <!-- 热门城市 -->
            <div class="flex flex-col gap-2">
              <div class="text-[10px] uppercase tracking-wider opacity-40 font-semibold">{{ $t('plugin.weather-widget.ui.popular_cities') }}</div>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="c in POPULAR_CITIES" :key="`p-${c.latitude}`"
                  class="px-3 py-1.5 rounded-full bg-white/[0.06] text-inherit cursor-pointer text-xs transition-colors hover:bg-white/[0.12] active:scale-95 border border-white/[0.06]"
                  @click="handleSelectCity(c)"
                >
                  {{ c.name }}
                </button>
              </div>
            </div>
          </div>

          <!-- ═══ 天气主视图 ═══ -->
          <div v-else key="weather" class="relative z-[2] flex flex-col wx-panel-scroll" style="max-height: 520px">

            <!-- 骨架屏 -->
            <template v-if="initialLoading && !current">
              <div class="p-5 flex flex-col gap-4">
                <div class="flex justify-between items-center">
                  <div class="wx-skeleton" style="width:80px;height:24px" />
                  <div class="flex gap-1.5"><div class="wx-skeleton" style="width:24px;height:24px;border-radius:50%" /><div class="wx-skeleton" style="width:24px;height:24px;border-radius:50%" /></div>
                </div>
                <div class="flex flex-col items-center gap-2 py-4">
                  <div class="wx-skeleton" style="width:100px;height:64px" />
                  <div class="wx-skeleton" style="width:120px;height:16px" />
                  <div class="wx-skeleton" style="width:80px;height:12px" />
                </div>
                <div class="wx-skeleton" style="width:100%;height:80px;border-radius:12px" />
                <div class="grid grid-cols-3 gap-2">
                  <div v-for="i in 6" :key="i" class="wx-skeleton" style="height:68px;border-radius:12px" />
                </div>
                <div class="wx-skeleton" style="width:100%;height:100px;border-radius:12px" />
              </div>
            </template>

            <!-- 错误（无缓存数据时） -->
            <div v-else-if="error && !current" class="p-5 flex flex-col items-center justify-center gap-3 text-center" style="min-height: 300px">
              <IconifyIcon icon="lucide:cloud-off" class="size-10 opacity-30" />
              <p class="text-sm opacity-70">{{ $t('plugin.weather-widget.ui.error') }}</p>
              <button
                class="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/[0.08] text-inherit cursor-pointer text-sm font-medium transition-colors hover:bg-white/[0.14] active:scale-95"
                @click="fetchAll"
              >
                <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" /> {{ $t('plugin.weather-widget.ui.retry') }}
              </button>
            </div>

            <!-- 天气内容 -->
            <template v-if="current">
              <!-- 头部：场景装饰 + 城市 + 温度 -->
              <div class="relative p-5 pb-3">
                <!-- 场景装饰 -->
                <div class="absolute inset-0 pointer-events-none overflow-hidden z-0">
                  <template v-if="bgInfo.scene === 'sun'">
                    <div class="wx-sun-glow" />
                  </template>
                  <template v-else-if="bgInfo.scene === 'moon-star'">
                    <div class="wx-moon-glow" />
                    <div class="wx-star-dot" style="top:12%;left:15%;animation-delay:0s" />
                    <div class="wx-star-dot" style="top:6%;left:40%;animation-delay:0.8s" />
                    <div class="wx-star-dot" style="top:20%;left:60%;animation-delay:1.5s" />
                    <div class="wx-star-dot" style="top:8%;left:80%;animation-delay:2.2s" />
                  </template>
                  <template v-else-if="bgInfo.scene === 'cloud'">
                    <div class="wx-cloud-glow" />
                  </template>
                  <template v-else-if="bgInfo.scene === 'rain'">
                    <div class="wx-rain-hint" />
                    <div class="wx-rain-hint" />
                    <div class="wx-rain-hint" />
                  </template>
                  <template v-else-if="bgInfo.scene === 'snow'">
                    <div class="wx-snow-hint" />
                    <div class="wx-snow-hint" />
                    <div class="wx-snow-hint" />
                  </template>
                  <template v-else-if="bgInfo.scene === 'thunder'">
                    <div class="wx-thunder-flash" />
                  </template>
                  <template v-else-if="bgInfo.scene === 'fog'">
                    <div class="wx-fog-layer" />
                    <div class="wx-fog-layer" />
                  </template>
                </div>

                <!-- 城市行 -->
                <div class="relative z-[1] flex justify-between items-center mb-2 wx-fade-up">
                  <button
                    class="flex items-center gap-1.5 bg-white/[0.08] rounded-full px-3 py-1 text-[13px] text-inherit cursor-pointer transition-all hover:bg-white/[0.14] active:scale-95 border border-white/[0.06]"
                    @click="showCitySelector = true"
                  >
                    <IconifyIcon icon="lucide:map-pin" class="size-3 opacity-60" />
                    <span class="font-medium max-w-[140px] truncate">{{ cityName }}</span>
                    <IconifyIcon icon="lucide:chevron-down" class="size-2.5 opacity-40" />
                  </button>
                  <div class="flex gap-1">
                    <button
                      class="flex items-center justify-center size-7 rounded-full text-inherit cursor-pointer transition-colors hover:bg-white/[0.1] active:scale-90 disabled:opacity-25"
                      :disabled="locating"
                      @click="geolocate"
                    >
                      <IconifyIcon :icon="locating ? 'lucide:loader-2' : 'lucide:locate'" :class="locating ? 'size-3.5 animate-spin' : 'size-3.5'" />
                    </button>
                    <button
                      class="flex items-center justify-center size-7 rounded-full text-inherit cursor-pointer transition-colors hover:bg-white/[0.1] active:scale-90 disabled:opacity-25"
                      :disabled="loading"
                      @click="fetchAll"
                    >
                      <IconifyIcon :icon="loading ? 'lucide:loader-2' : 'lucide:refresh-cw'" :class="loading ? 'size-3.5 animate-spin' : 'size-3.5'" />
                    </button>
                  </div>
                </div>

                <!-- 主温度 -->
                <div class="relative z-[1] flex flex-col items-center py-3 wx-fade-up wx-fade-up-1">
                  <div class="flex items-center justify-center gap-4">
                    <div class="text-[64px] font-extralight leading-none tracking-[-3px]" style="text-shadow: 0 2px 20px rgba(0,0,0,0.12)">
                      {{ current.temperature !== null ? Math.round(current.temperature) : '--' }}°
                    </div>
                    <IconifyIcon :icon="`lucide:${getIcon(current.weather_code, current.is_day)}`" class="wx-hero-icon" />
                  </div>
                  <div class="flex items-center gap-2 mt-2">
                    <span class="text-[13px] font-medium opacity-85">{{ weatherText(current) }}</span>
                  </div>
                  <div class="flex items-center gap-3 mt-1 text-xs opacity-50 tabular-nums">
                    <span v-if="todayForecast">H:{{ todayForecast.temp_max !== null ? Math.round(todayForecast.temp_max) : '--' }}°</span>
                    <span v-if="todayForecast">L:{{ todayForecast.temp_min !== null ? Math.round(todayForecast.temp_min) : '--' }}°</span>
                  </div>
                </div>

                <!-- 过期提示 -->
                <div v-if="isStale" class="relative z-[1] text-center text-[10px] opacity-40 mt-1">
                  {{ $t('plugin.weather-widget.ui.data_stale') }}
                </div>
              </div>

              <!-- 内容区域 -->
              <div class="px-4 pb-4 flex flex-col gap-3">

                <!-- 24小时预报 -->
                <div v-if="hourly.length > 0" class="wx-acrylic wx-noise relative overflow-hidden wx-fade-up wx-fade-up-2">
                  <div ref="hourlyScrollRef" class="wx-hourly-scroll">
                    <div
                      v-for="(h, idx) in hourly"
                      :key="idx"
                      class="wx-hourly-item"
                      :class="h.is_current ? 'wx-hourly-item--current' : ''"
                    >
                      <span class="text-[10px] opacity-60" :class="h.is_current ? 'font-semibold opacity-90' : ''">
                        {{ formatTime(h.time, h.is_current) }}
                      </span>
                      <IconifyIcon :icon="`lucide:${getIcon(h.weather_code, current.is_day)}`" class="size-4 opacity-80" />
                      <span class="text-[13px] font-semibold tabular-nums">
                        {{ h.temperature !== null ? `${Math.round(h.temperature)}°` : '--' }}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- 指标网格 2x3 -->
                <div class="grid grid-cols-3 gap-2 wx-fade-up wx-fade-up-3">
                  <!-- 体感温度 -->
                  <div class="wx-acrylic wx-noise wx-metric-feels relative flex flex-col items-center gap-1 py-3 px-1">
                    <IconifyIcon icon="lucide:thermometer" class="size-3.5 opacity-55" />
                    <span class="text-[15px] font-bold leading-none tabular-nums">
                      {{ current.apparent_temperature !== null ? `${Math.round(current.apparent_temperature)}°` : '--' }}
                    </span>
                    <span class="text-[10px] opacity-50">{{ $t('plugin.weather-widget.ui.feels_like') }}</span>
                  </div>
                  <!-- 湿度 -->
                  <div class="wx-acrylic wx-noise wx-metric-humidity relative flex flex-col items-center gap-1 py-3 px-1">
                    <IconifyIcon icon="lucide:droplets" class="size-3.5 opacity-55" />
                    <span class="text-[15px] font-bold leading-none tabular-nums">{{ current.humidity ?? '--' }}%</span>
                    <span class="text-[10px] opacity-50">{{ $t('plugin.weather-widget.ui.humidity') }}</span>
                  </div>
                  <!-- 风速 -->
                  <div class="wx-acrylic wx-noise wx-metric-wind relative flex flex-col items-center gap-1 py-3 px-1">
                    <IconifyIcon icon="lucide:wind" class="size-3.5 opacity-55" />
                    <span class="text-[15px] font-bold leading-none tabular-nums">{{ current.wind_speed ?? '--' }}</span>
                    <span class="text-[10px] opacity-50">km/h</span>
                  </div>
                  <!-- UV -->
                  <div class="wx-acrylic wx-noise wx-metric-uv relative flex flex-col items-center gap-1 py-3 px-1">
                    <IconifyIcon icon="lucide:sun-dim" class="size-3.5 opacity-55" />
                    <span class="text-[15px] font-bold leading-none tabular-nums">{{ current.uv_index ?? '--' }}</span>
                    <span class="text-[10px] opacity-50">UV</span>
                  </div>
                  <!-- AQI -->
                  <div class="wx-acrylic wx-noise wx-metric-aqi relative flex flex-col items-center gap-1 py-3 px-1">
                    <IconifyIcon icon="lucide:leaf" class="size-3.5 opacity-55" />
                    <span class="text-[15px] font-bold leading-none" :style="{ color: aqiColor(airQuality?.aqi) }">
                      {{ aqiLevel(airQuality?.aqi) }}
                    </span>
                    <span class="text-[10px] opacity-50">{{ $t('plugin.weather-widget.ui.aqi') }}</span>
                  </div>
                  <!-- 日出/日落 -->
                  <div class="wx-acrylic wx-noise wx-metric-sun relative flex flex-col items-center gap-1 py-3 px-1">
                    <IconifyIcon :icon="current.is_day ? 'lucide:sunrise' : 'lucide:sunset'" class="size-3.5 opacity-55" />
                    <span class="text-[15px] font-bold leading-none tabular-nums">
                      {{ current.is_day ? formatSunTime(todayForecast?.sunrise) : formatSunTime(todayForecast?.sunset) }}
                    </span>
                    <span class="text-[10px] opacity-50">
                      {{ current.is_day ? $t('plugin.weather-widget.ui.sunrise') : $t('plugin.weather-widget.ui.sunset') }}
                    </span>
                  </div>
                </div>

                <!-- 多日预报 -->
                <div v-if="forecast.length > 0" class="wx-acrylic wx-noise relative overflow-hidden wx-fade-up wx-fade-up-4">
                  <div
                    v-for="(day, index) in forecast"
                    :key="day.date"
                    class="flex items-center px-3.5 py-2.5 text-[13px]"
                    :class="index < forecast.length - 1 ? 'border-b border-white/[0.06]' : ''"
                  >
                    <span class="w-9 font-semibold shrink-0">{{ formatDate(day.date, index) }}</span>
                    <span class="w-8 text-[11px] opacity-40 shrink-0">{{ formatWeekday(day.date) }}</span>
                    <IconifyIcon :icon="`lucide:${getIcon(day.weather_code)}`" class="size-4 mx-1.5 opacity-70 shrink-0" />
                    <span class="opacity-45 w-7 text-right tabular-nums shrink-0 text-xs">{{ day.temp_min !== null ? Math.round(day.temp_min) : '--' }}°</span>
                    <div class="flex-1 mx-2 wx-temp-bar-track">
                      <div class="wx-temp-bar-fill" :style="tempBarStyle(day.temp_min, day.temp_max)" />
                    </div>
                    <span class="font-semibold w-7 text-right tabular-nums shrink-0 text-xs">{{ day.temp_max !== null ? Math.round(day.temp_max) : '--' }}°</span>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </Transition>
      </div>
    </template>
  </Popover>
</template>
