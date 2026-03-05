<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';
import { Popover, Tooltip } from 'ant-design-vue';
import { IconifyIcon, $t } from '@novus/plugin-shared';

import type { CityInfo } from './use-weather';
import { useWeather, POPULAR_CITIES } from './use-weather';
import { getWeatherCodeInfo, getWeatherBg } from './weather-codes';

const {
  cityName, recentCities, current, forecast, loading, error,
  locating, showCitySelector, fetchAll, searchCity, selectCity, geolocate,
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
  }, 300);
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

const todayForecast = computed(() => forecast.value?.[0] ?? null);

function tempBarStyle(min: number | null, max: number | null): Record<string, string> {
  if (min === null || max === null || !forecast.value.length) return {};
  const allMin = Math.min(...forecast.value.map(d => d.temp_min ?? 99));
  const allMax = Math.max(...forecast.value.map(d => d.temp_max ?? -99));
  const range = allMax - allMin || 1;
  const left = ((min - allMin) / range) * 100;
  const width = ((max - min) / range) * 100;
  return {
    left: `${left}%`,
    width: `${Math.max(width, 8)}%`,
  };
}
</script>

<template>
  <Popover
    v-model:open="popoverOpen"
    trigger="click"
    placement="bottomRight"
    :arrow="false"
    overlay-class-name="weather-popover-immersive"
  >
    <!-- 触发按钮 -->
    <template #default>
      <Tooltip :title="$t('plugin.weather-widget.ui.temperature')" placement="bottom">
        <div class="flex items-center gap-1 px-2 py-1 rounded-md cursor-pointer transition-colors hover:bg-accent">
          <template v-if="current && !loading">
            <IconifyIcon :icon="`lucide:${getIcon(current.weather_code, current.is_day)}`" class="size-4 text-primary" />
            <span class="text-[13px] font-semibold hidden sm:inline">{{ current.temperature !== null ? `${Math.round(current.temperature)}°` : '--' }}</span>
          </template>
          <template v-else-if="loading">
            <IconifyIcon icon="lucide:loader-2" class="size-4 animate-spin text-muted-foreground" />
          </template>
          <template v-else>
            <IconifyIcon icon="lucide:cloud-off" class="size-4 text-muted-foreground" />
          </template>
        </div>
      </Tooltip>
    </template>

    <!-- 沉浸式面板 -->
    <template #content>
      <div
        class="relative rounded-2xl overflow-hidden text-white font-sans" style="width: 340px"
        :class="current ? getBg(current.weather_code, current.is_day).bgClass : 'wx-bg--cloudy-day'"
      >
        <!-- 天气场景动画层 -->
        <div v-if="current" class="absolute inset-0 pointer-events-none overflow-hidden z-[1]">
          <!-- 晴天：太阳光晕 + 光线 -->
          <template v-if="getBg(current.weather_code, current.is_day).scene === 'sun'">
            <div class="wx-sun" />
            <div class="wx-sun-ray" />
          </template>

          <!-- 晴夜：月亮 + 星星 -->
          <template v-else-if="getBg(current.weather_code, current.is_day).scene === 'moon-star'">
            <div class="wx-moon" />
            <div class="wx-star" style="top: 15%; left: 12%; animation-delay: 0s" />
            <div class="wx-star" style="top: 8%; left: 35%; animation-delay: 0.8s" />
            <div class="wx-star" style="top: 22%; left: 55%; animation-delay: 1.5s" />
            <div class="wx-star" style="top: 5%; left: 75%; animation-delay: 2.1s" />
            <div class="wx-star" style="top: 28%; left: 25%; animation-delay: 0.4s" />
            <div class="wx-star" style="top: 12%; left: 90%; animation-delay: 1.2s" />
          </template>

          <!-- 多云：漂浮云朵 -->
          <template v-else-if="getBg(current.weather_code, current.is_day).scene === 'cloud'">
            <div class="wx-cloud wx-cloud--lg" />
            <div class="wx-cloud wx-cloud--md" />
            <div class="wx-cloud wx-cloud--sm" />
          </template>

          <!-- 下雨：雨滴 + 乌云 -->
          <template v-else-if="getBg(current.weather_code, current.is_day).scene === 'rain'">
            <div class="wx-rain-cloud wx-rain-cloud--1" />
            <div class="wx-rain-cloud wx-rain-cloud--2" />
            <div v-for="i in 14" :key="'r'+i" class="wx-rain" :style="{ '--i': i }" />
          </template>

          <!-- 下雪：雪花 + 浅云 -->
          <template v-else-if="getBg(current.weather_code, current.is_day).scene === 'snow'">
            <div class="wx-snow-cloud wx-snow-cloud--1" />
            <div v-for="i in 12" :key="'s'+i" class="wx-snow" :style="{ '--i': i }" />
          </template>

          <!-- 雷暴：闪电 + 闪光 + 雨 + 乌云 -->
          <template v-else-if="getBg(current.weather_code, current.is_day).scene === 'thunder'">
            <div class="wx-lightning" />
            <div class="wx-bolt" />
            <div class="wx-rain-cloud wx-rain-cloud--1" />
            <div class="wx-rain-cloud wx-rain-cloud--2" />
            <div v-for="i in 14" :key="'tr'+i" class="wx-rain" :style="{ '--i': i }" />
          </template>

          <!-- 雾：飘动雾气层 -->
          <template v-else-if="getBg(current.weather_code, current.is_day).scene === 'fog'">
            <div class="wx-fog wx-fog--1" />
            <div class="wx-fog wx-fog--2" />
            <div class="wx-fog wx-fog--3" />
          </template>
        </div>

        <Transition name="wx-view" mode="out-in">
        <!-- 城市选择视图 -->
        <div v-if="showCitySelector" key="city" class="relative z-[2] p-4 flex flex-col gap-3 min-h-[380px]">
          <div class="flex justify-between items-center">
            <span class="text-base font-semibold tracking-wide">{{ $t('plugin.weather-widget.ui.change_city') }}</span>
            <button class="flex items-center justify-center size-8 rounded-full bg-white/[0.10] text-inherit cursor-pointer transition-colors hover:bg-white/[0.20] active:scale-95" @click="showCitySelector = false">
              <IconifyIcon icon="lucide:x" class="size-4" />
            </button>
          </div>

          <!-- 搜索 -->
          <div class="flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-white/[0.08]">
            <IconifyIcon icon="lucide:search" class="size-4 opacity-60" />
            <input
              :value="searchKeyword"
              :placeholder="$t('plugin.weather-widget.ui.search_city')"
              class="flex-1 bg-transparent border-none outline-none text-inherit text-sm placeholder:text-white/40"
              @input="handleSearchInput(($event.target as HTMLInputElement).value)"
            />
          </div>

          <!-- 搜索结果 -->
          <div v-if="searchKeyword.trim()" class="flex flex-col gap-1 max-h-44 overflow-y-auto">
            <div v-if="searching" class="flex items-center gap-2 py-3 justify-center text-xs opacity-70">
              <IconifyIcon icon="lucide:loader-2" class="size-4 animate-spin" /> {{ $t('plugin.weather-widget.ui.loading') }}
            </div>
            <button
              v-for="c in searchResults" :key="`${c.latitude}-${c.longitude}`"
              class="flex items-center gap-2 px-3.5 py-2.5 rounded-xl border-none bg-white/[0.08] text-inherit cursor-pointer text-sm text-left transition-all hover:bg-white/[0.18] active:scale-[0.98]"
              @click="handleSelectCity(c)"
            >
              <IconifyIcon icon="lucide:map-pin" class="size-4 opacity-50 shrink-0" />
              <span>{{ c.name }}</span>
              <span v-if="c.admin1" class="opacity-50 text-xs">{{ c.admin1 }}</span>
            </button>
            <div v-if="!searching && searchResults.length === 0" class="flex items-center gap-2 py-3 justify-center text-xs opacity-60">
              {{ $t('plugin.weather-widget.error.city_not_found') }}
            </div>
          </div>

          <!-- 定位按钮 -->
          <button class="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.08] text-inherit cursor-pointer text-sm justify-center font-medium transition-colors hover:bg-white/[0.16] active:scale-[0.98] disabled:opacity-30 disabled:cursor-default" @click="geolocate" :disabled="locating">
            <IconifyIcon :icon="locating ? 'lucide:loader-2' : 'lucide:locate'" :class="locating ? 'size-4 animate-spin' : 'size-4'" />
            {{ locating ? $t('plugin.weather-widget.ui.locating') : $t('plugin.weather-widget.ui.auto_locate') }}
          </button>

          <!-- 最近城市 -->
          <div v-if="recentCities.length > 0" class="flex flex-col gap-2">
            <div class="text-[11px] uppercase tracking-wider opacity-50 font-semibold">{{ $t('plugin.weather-widget.ui.recent_cities') }}</div>
            <div class="flex flex-wrap gap-2">
              <button v-for="c in recentCities" :key="`r-${c.latitude}`" class="px-3.5 py-1.5 rounded-full bg-white/[0.08] text-inherit cursor-pointer text-xs font-medium transition-colors hover:bg-white/[0.16] active:scale-95" @click="handleSelectCity(c)">
                {{ c.name }}
              </button>
            </div>
          </div>

          <!-- 热门城市 -->
          <div class="flex flex-col gap-2">
            <div class="text-[11px] uppercase tracking-wider opacity-50 font-semibold">{{ $t('plugin.weather-widget.ui.popular_cities') }}</div>
            <div class="flex flex-wrap gap-2">
              <button v-for="c in POPULAR_CITIES" :key="`p-${c.latitude}`" class="px-3.5 py-1.5 rounded-full bg-white/[0.08] text-inherit cursor-pointer text-xs font-medium transition-colors hover:bg-white/[0.16] active:scale-95" @click="handleSelectCity(c)">
                {{ c.name }}
              </button>
            </div>
          </div>
        </div>

        <!-- 天气主视图 -->
        <div v-else key="weather" class="relative z-[2] p-5 flex flex-col">
          <!-- 错误 -->
          <div v-if="error && !current" class="flex flex-col items-center justify-center px-6 py-14 gap-3 text-center">
            <IconifyIcon icon="lucide:cloud-off" class="size-12 opacity-40" />
            <p class="text-sm opacity-80">{{ $t('plugin.weather-widget.ui.error') }}</p>
            <button class="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/[0.10] text-inherit cursor-pointer text-sm font-medium transition-colors hover:bg-white/[0.18] active:scale-95" @click="fetchAll">
              <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" /> {{ $t('plugin.weather-widget.ui.retry') }}
            </button>
          </div>

          <!-- 天气内容 -->
          <template v-if="current">
            <!-- 城市 + 操作 -->
            <div class="flex justify-between items-center mb-1">
              <button class="flex items-center gap-1.5 bg-white/[0.10] rounded-full px-3 py-1.5 text-sm text-inherit cursor-pointer transition-colors hover:bg-white/[0.18] active:scale-95" @click="showCitySelector = true">
                <IconifyIcon icon="lucide:map-pin" class="size-3.5 opacity-70" />
                <span class="font-medium">{{ cityName }}</span>
                <IconifyIcon icon="lucide:chevron-down" class="size-3 opacity-50" />
              </button>
              <div class="flex gap-1">
                <button class="flex items-center justify-center size-7 rounded-full text-inherit cursor-pointer transition-colors hover:bg-white/[0.15] active:scale-90 disabled:opacity-30 disabled:cursor-default" @click="geolocate" :disabled="locating">
                  <IconifyIcon :icon="locating ? 'lucide:loader-2' : 'lucide:locate'" :class="locating ? 'size-3.5 animate-spin' : 'size-3.5'" />
                </button>
                <button class="flex items-center justify-center size-7 rounded-full text-inherit cursor-pointer transition-colors hover:bg-white/[0.15] active:scale-90 disabled:opacity-30 disabled:cursor-default" @click="fetchAll" :disabled="loading">
                  <IconifyIcon :icon="loading ? 'lucide:loader-2' : 'lucide:refresh-cw'" :class="loading ? 'size-3.5 animate-spin' : 'size-3.5'" />
                </button>
              </div>
            </div>

            <!-- 主温度区域 -->
            <div class="flex flex-col items-center py-5">
              <div class="text-[68px] font-extralight leading-none tracking-[-2px] [text-shadow:0_2px_16px_rgba(0,0,0,0.15)]">{{ current.temperature !== null ? Math.round(current.temperature) : '--' }}°</div>
              <div class="flex items-center gap-2 mt-2.5">
                <IconifyIcon :icon="`lucide:${getIcon(current.weather_code, current.is_day)}`" class="size-5 drop-shadow" />
                <span class="text-sm font-medium opacity-90">{{ weatherText(current) }}</span>
              </div>
              <div v-if="todayForecast" class="flex items-center gap-2 mt-1 text-xs opacity-60 tabular-nums">
                <span>H:{{ todayForecast.temp_max !== null ? Math.round(todayForecast.temp_max) : '--' }}°</span>
                <span>L:{{ todayForecast.temp_min !== null ? Math.round(todayForecast.temp_min) : '--' }}°</span>
              </div>
            </div>

            <!-- 指标卡片 -->
            <div class="grid grid-cols-3 gap-2 mb-4">
              <div class="flex flex-col items-center gap-1 py-3 rounded-xl bg-white/[0.07]">
                <IconifyIcon icon="lucide:droplets" class="size-3.5 opacity-50" />
                <span class="text-base font-semibold leading-none">{{ current.humidity ?? '--' }}%</span>
                <span class="text-[10px] opacity-40">{{ $t('plugin.weather-widget.ui.humidity') }}</span>
              </div>
              <div class="flex flex-col items-center gap-1 py-3 rounded-xl bg-white/[0.07]">
                <IconifyIcon icon="lucide:wind" class="size-3.5 opacity-50" />
                <span class="text-base font-semibold leading-none">{{ current.wind_speed ?? '--' }}</span>
                <span class="text-[10px] opacity-40">km/h</span>
              </div>
              <div class="flex flex-col items-center gap-1 py-3 rounded-xl bg-white/[0.07]">
                <IconifyIcon icon="lucide:sun-dim" class="size-3.5 opacity-50" />
                <span class="text-base font-semibold leading-none">{{ current.uv_index ?? '--' }}</span>
                <span class="text-[10px] opacity-40">UV</span>
              </div>
            </div>

            <!-- 多日预报 -->
            <div v-if="forecast.length > 0" class="flex flex-col bg-white/[0.06] rounded-xl overflow-hidden">
              <div
                v-for="(day, index) in forecast"
                :key="day.date"
                class="flex items-center px-4 py-3 text-sm"
                :class="index < forecast.length - 1 ? 'border-b border-white/[0.08]' : ''"
              >
                <span class="w-10 font-semibold shrink-0">{{ formatDate(day.date, index) }}</span>
                <span class="w-9 text-xs opacity-50 shrink-0">{{ formatWeekday(day.date) }}</span>
                <IconifyIcon :icon="`lucide:${getIcon(day.weather_code)}`" class="size-5 mx-2 opacity-80 shrink-0" />
                <span class="opacity-50 w-7 text-right tabular-nums shrink-0">{{ day.temp_min !== null ? Math.round(day.temp_min) : '--' }}°</span>
                <div class="flex-1 mx-2.5 relative overflow-hidden" style="height: 4px; border-radius: 9999px; background: rgba(255,255,255,0.08)">
                  <div
                    class="absolute top-0"
                    :style="{ ...tempBarStyle(day.temp_min, day.temp_max), height: '100%', borderRadius: '9999px', background: 'linear-gradient(to right, rgba(147,197,253,0.8), rgba(253,224,171,0.8), rgba(252,165,115,0.7))' }"
                  />
                </div>
                <span class="font-semibold w-7 text-right tabular-nums shrink-0">{{ day.temp_max !== null ? Math.round(day.temp_max) : '--' }}°</span>
              </div>
            </div>
          </template>
        </div>
        </Transition>
      </div>
    </template>
  </Popover>
</template>

<!-- 布局/排版使用 Tailwind；仅 Popover 覆盖、天气渐变、粒子动画通过 styles.ts JS 注入 -->
