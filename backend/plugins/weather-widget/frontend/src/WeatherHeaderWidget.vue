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
        class="relative w-[340px] min-h-[360px] rounded-2xl overflow-hidden text-white font-sans"
        :class="current ? getBg(current.weather_code, current.is_day).bgClass : 'wx-bg--cloudy-day'"
      >
        <!-- 粒子动画层 -->
        <div v-if="current" class="absolute inset-0 pointer-events-none overflow-hidden z-[1]">
          <template v-if="getBg(current.weather_code, current.is_day).particles === 'rain'">
            <div v-for="i in 20" :key="'r'+i" class="wx-rain" :style="{ '--i': i }" />
          </template>
          <template v-else-if="getBg(current.weather_code, current.is_day).particles === 'snow'">
            <div v-for="i in 15" :key="'s'+i" class="wx-snow" :style="{ '--i': i }" />
          </template>
          <template v-else-if="getBg(current.weather_code, current.is_day).particles === 'cloud'">
            <div class="wx-cloud wx-cloud--1" />
            <div class="wx-cloud wx-cloud--2" />
          </template>
        </div>

        <!-- 城市选择视图 -->
        <div v-if="showCitySelector" class="relative z-[2] p-4 flex flex-col gap-3 min-h-[360px]">
          <div class="flex justify-between items-center">
            <span class="text-[15px] font-semibold">{{ $t('plugin.weather-widget.ui.change_city') }}</span>
            <button class="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-white/20 bg-white/[0.12] backdrop-blur text-inherit cursor-pointer text-xs transition-colors hover:bg-white/[0.22]" @click="showCitySelector = false">
              <IconifyIcon icon="lucide:x" class="size-4" />
            </button>
          </div>

          <!-- 搜索 -->
          <div class="flex items-center gap-2 px-3 py-2 rounded-[10px] bg-white/[0.12] border border-white/20">
            <IconifyIcon icon="lucide:search" class="size-3.5 opacity-70" />
            <input
              :value="searchKeyword"
              :placeholder="$t('plugin.weather-widget.ui.search_city')"
              class="flex-1 bg-transparent border-none outline-none text-inherit text-[13px] placeholder:text-white/50"
              @input="handleSearchInput(($event.target as HTMLInputElement).value)"
            />
          </div>

          <!-- 搜索结果 -->
          <div v-if="searchKeyword.trim()" class="flex flex-col gap-0.5 max-h-40 overflow-y-auto">
            <div v-if="searching" class="flex items-center gap-1.5 py-2 justify-center text-xs opacity-70">
              <IconifyIcon icon="lucide:loader-2" class="size-3.5 animate-spin" /> {{ $t('plugin.weather-widget.ui.loading') }}
            </div>
            <button
              v-for="c in searchResults" :key="`${c.latitude}-${c.longitude}`"
              class="flex items-center gap-1.5 px-3 py-2 rounded-lg border-none bg-white/[0.08] text-inherit cursor-pointer text-[13px] text-left transition-colors hover:bg-white/[0.18]"
              @click="handleSelectCity(c)"
            >
              <IconifyIcon icon="lucide:map-pin" class="size-3.5 opacity-60" />
              {{ c.name }}<span v-if="c.admin1" class="opacity-60">, {{ c.admin1 }}</span>
            </button>
            <div v-if="!searching && searchResults.length === 0" class="flex items-center gap-1.5 py-2 justify-center text-xs opacity-70">
              {{ $t('plugin.weather-widget.error.city_not_found') }}
            </div>
          </div>

          <!-- 定位按钮 -->
          <button class="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/15 border border-white/20 text-inherit cursor-pointer text-[13px] justify-center font-medium transition-colors hover:bg-white/[0.18] disabled:opacity-50 disabled:cursor-default" @click="geolocate" :disabled="locating">
            <IconifyIcon :icon="locating ? 'lucide:loader-2' : 'lucide:locate'" :class="locating ? 'size-4 animate-spin' : 'size-4'" />
            {{ locating ? $t('plugin.weather-widget.ui.locating') : $t('plugin.weather-widget.ui.auto_locate') }}
          </button>

          <!-- 最近城市 -->
          <div v-if="recentCities.length > 0" class="flex flex-col gap-1.5">
            <div class="text-[11px] opacity-60 font-medium">{{ $t('plugin.weather-widget.ui.recent_cities') }}</div>
            <div class="flex flex-wrap gap-1.5">
              <button v-for="c in recentCities" :key="`r-${c.latitude}`" class="px-3 py-1 rounded-2xl border border-white/20 bg-white/10 text-inherit cursor-pointer text-xs transition-all hover:bg-white/[0.22] active:scale-95" @click="handleSelectCity(c)">
                {{ c.name }}
              </button>
            </div>
          </div>

          <!-- 热门城市 -->
          <div class="flex flex-col gap-1.5">
            <div class="text-[11px] opacity-60 font-medium">{{ $t('plugin.weather-widget.ui.popular_cities') }}</div>
            <div class="flex flex-wrap gap-1.5">
              <button v-for="c in POPULAR_CITIES" :key="`p-${c.latitude}`" class="px-3 py-1 rounded-2xl border border-white/20 bg-white/10 text-inherit cursor-pointer text-xs transition-all hover:bg-white/[0.22] active:scale-95" @click="handleSelectCity(c)">
                {{ c.name }}
              </button>
            </div>
          </div>
        </div>

        <!-- 天气主视图 -->
        <div v-else class="relative z-[2] p-4 flex flex-col gap-3.5">
          <!-- 错误 -->
          <div v-if="error && !current" class="flex flex-col items-center justify-center px-5 py-10 gap-2.5 text-center">
            <IconifyIcon icon="lucide:cloud-off" class="size-10 opacity-50" />
            <p>{{ $t('plugin.weather-widget.ui.error') }}</p>
            <button class="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-white/20 bg-white/[0.12] backdrop-blur text-inherit cursor-pointer text-xs transition-colors hover:bg-white/[0.22]" @click="fetchAll">
              <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" /> {{ $t('plugin.weather-widget.ui.retry') }}
            </button>
          </div>

          <!-- 天气内容 -->
          <template v-if="current">
            <!-- 城市 + 操作 -->
            <div class="flex justify-between items-center">
              <button class="flex items-center gap-1 bg-white/15 backdrop-blur border border-white/20 rounded-[20px] px-3 py-1 text-[13px] text-inherit cursor-pointer transition-colors hover:bg-white/25" @click="showCitySelector = true">
                <IconifyIcon icon="lucide:map-pin" class="size-3.5" />
                <span>{{ cityName }}</span>
                <IconifyIcon icon="lucide:chevron-down" class="size-3" />
              </button>
              <div class="flex gap-1">
                <button class="flex items-center justify-center size-7 rounded-lg border border-white/20 bg-white/10 backdrop-blur text-inherit cursor-pointer transition-colors hover:bg-white/20 disabled:opacity-50 disabled:cursor-default" @click="geolocate" :disabled="locating">
                  <IconifyIcon :icon="locating ? 'lucide:loader-2' : 'lucide:locate'" :class="locating ? 'size-3.5 animate-spin' : 'size-3.5'" />
                </button>
                <button class="flex items-center justify-center size-7 rounded-lg border border-white/20 bg-white/10 backdrop-blur text-inherit cursor-pointer transition-colors hover:bg-white/20 disabled:opacity-50 disabled:cursor-default" @click="fetchAll" :disabled="loading">
                  <IconifyIcon :icon="loading ? 'lucide:loader-2' : 'lucide:refresh-cw'" :class="loading ? 'size-3.5 animate-spin' : 'size-3.5'" />
                </button>
              </div>
            </div>

            <!-- 主温度 -->
            <div class="text-center py-2">
              <div class="text-[56px] font-extralight leading-none tracking-[-2px] [text-shadow:0_2px_8px_rgba(0,0,0,0.15)]">{{ current.temperature !== null ? Math.round(current.temperature) : '--' }}°</div>
              <div class="flex items-center justify-center gap-1.5 text-sm opacity-90 mt-1">
                <IconifyIcon :icon="`lucide:${getIcon(current.weather_code, current.is_day)}`" class="size-6" />
                <span>{{ weatherText(current) }}</span>
              </div>
            </div>

            <!-- 指标卡片 -->
            <div class="grid grid-cols-3 gap-2">
              <div class="flex flex-col items-center gap-0.5 px-1.5 py-2.5 rounded-xl bg-white/[0.12] backdrop-blur border border-white/15">
                <IconifyIcon icon="lucide:droplets" class="size-4 text-blue-300" />
                <span class="text-[15px] font-semibold">{{ current.humidity ?? '--' }}%</span>
                <span class="text-[10px] opacity-70">{{ $t('plugin.weather-widget.ui.humidity') }}</span>
              </div>
              <div class="flex flex-col items-center gap-0.5 px-1.5 py-2.5 rounded-xl bg-white/[0.12] backdrop-blur border border-white/15">
                <IconifyIcon icon="lucide:wind" class="size-4 text-cyan-200" />
                <span class="text-[15px] font-semibold">{{ current.wind_speed ?? '--' }}</span>
                <span class="text-[10px] opacity-70">km/h</span>
              </div>
              <div class="flex flex-col items-center gap-0.5 px-1.5 py-2.5 rounded-xl bg-white/[0.12] backdrop-blur border border-white/15">
                <IconifyIcon icon="lucide:sun-dim" class="size-4 text-amber-300" />
                <span class="text-[15px] font-semibold">{{ current.uv_index ?? '--' }}</span>
                <span class="text-[10px] opacity-70">UV</span>
              </div>
            </div>

            <!-- 多日预报 -->
            <div v-if="forecast.length > 0" class="flex flex-col gap-0.5 bg-white/[0.08] backdrop-blur rounded-xl border border-white/[0.12] px-3 py-2">
              <div
                v-for="(day, index) in forecast"
                :key="day.date"
                class="flex items-center py-[5px] text-[13px]"
              >
                <span class="w-[42px] font-medium">{{ formatDate(day.date, index) }}</span>
                <span class="w-8 text-[11px] opacity-60">{{ formatWeekday(day.date) }}</span>
                <IconifyIcon :icon="`lucide:${getIcon(day.weather_code)}`" class="mx-2 size-[18px]" />
                <span class="ml-auto flex gap-2">
                  <span class="font-semibold">{{ day.temp_max !== null ? Math.round(day.temp_max) : '--' }}°</span>
                  <span class="opacity-60">{{ day.temp_min !== null ? Math.round(day.temp_min) : '--' }}°</span>
                </span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </template>
  </Popover>
</template>

<!-- 布局/排版使用 Tailwind；仅 Popover 覆盖、天气渐变、粒子动画通过 styles.ts JS 注入 -->
