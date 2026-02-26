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
        <div class="wx-trigger">
          <template v-if="current && !loading">
            <IconifyIcon :icon="`lucide:${getIcon(current.weather_code, current.is_day)}`" class="size-4 text-primary" />
            <span class="wx-trigger__temp">{{ current.temperature !== null ? `${Math.round(current.temperature)}°` : '--' }}</span>
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
        class="wx-panel"
        :class="current ? getBg(current.weather_code, current.is_day).bgClass : 'wx-bg--cloudy-day'"
      >
        <!-- 粒子动画层 -->
        <div v-if="current" class="wx-particles">
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
        <div v-if="showCitySelector" class="wx-city-view">
          <div class="wx-city-view__header">
            <span class="wx-city-view__title">{{ $t('plugin.weather-widget.ui.change_city') }}</span>
            <button class="wx-glass-btn" @click="showCitySelector = false">
              <IconifyIcon icon="lucide:x" class="size-4" />
            </button>
          </div>

          <!-- 搜索 -->
          <div class="wx-city-view__search">
            <IconifyIcon icon="lucide:search" class="size-3.5" style="opacity: 0.7;" />
            <input
              :value="searchKeyword"
              :placeholder="$t('plugin.weather-widget.ui.search_city')"
              class="wx-city-view__input"
              @input="handleSearchInput(($event.target as HTMLInputElement).value)"
            />
          </div>

          <!-- 搜索结果 -->
          <div v-if="searchKeyword.trim()" class="wx-city-view__results">
            <div v-if="searching" class="wx-city-view__hint">
              <IconifyIcon icon="lucide:loader-2" class="size-3.5 animate-spin" /> {{ $t('plugin.weather-widget.ui.loading') }}
            </div>
            <button
              v-for="c in searchResults" :key="`${c.latitude}-${c.longitude}`"
              class="wx-city-btn wx-city-btn--result"
              @click="handleSelectCity(c)"
            >
              <IconifyIcon icon="lucide:map-pin" class="size-3.5" style="opacity: 0.6;" />
              {{ c.name }}<span v-if="c.admin1" style="opacity: 0.6;">, {{ c.admin1 }}</span>
            </button>
            <div v-if="!searching && searchResults.length === 0" class="wx-city-view__hint">
              {{ $t('plugin.weather-widget.error.city_not_found') }}
            </div>
          </div>

          <!-- 定位按钮 -->
          <button class="wx-city-btn wx-city-btn--locate" @click="geolocate" :disabled="locating">
            <IconifyIcon :icon="locating ? 'lucide:loader-2' : 'lucide:locate'" :class="locating ? 'size-4 animate-spin' : 'size-4'" />
            {{ locating ? $t('plugin.weather-widget.ui.locating') : $t('plugin.weather-widget.ui.auto_locate') }}
          </button>

          <!-- 最近城市 -->
          <div v-if="recentCities.length > 0" class="wx-city-view__section">
            <div class="wx-city-view__label">{{ $t('plugin.weather-widget.ui.recent_cities') }}</div>
            <div class="wx-city-grid">
              <button v-for="c in recentCities" :key="`r-${c.latitude}`" class="wx-city-chip" @click="handleSelectCity(c)">
                {{ c.name }}
              </button>
            </div>
          </div>

          <!-- 热门城市 -->
          <div class="wx-city-view__section">
            <div class="wx-city-view__label">{{ $t('plugin.weather-widget.ui.popular_cities') }}</div>
            <div class="wx-city-grid">
              <button v-for="c in POPULAR_CITIES" :key="`p-${c.latitude}`" class="wx-city-chip" @click="handleSelectCity(c)">
                {{ c.name }}
              </button>
            </div>
          </div>
        </div>

        <!-- 天气主视图 -->
        <div v-else class="wx-main">
          <!-- 错误 -->
          <div v-if="error && !current" class="wx-main__error">
            <IconifyIcon icon="lucide:cloud-off" class="size-10" style="opacity: 0.5;" />
            <p>{{ $t('plugin.weather-widget.ui.error') }}</p>
            <button class="wx-glass-btn" @click="fetchAll">
              <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" /> {{ $t('plugin.weather-widget.ui.retry') }}
            </button>
          </div>

          <!-- 天气内容 -->
          <template v-if="current">
            <!-- 城市 + 操作 -->
            <div class="wx-main__top">
              <button class="wx-main__city" @click="showCitySelector = true">
                <IconifyIcon icon="lucide:map-pin" class="size-3.5" />
                <span>{{ cityName }}</span>
                <IconifyIcon icon="lucide:chevron-down" class="size-3" />
              </button>
              <div class="wx-main__actions">
                <button class="wx-glass-icon" @click="geolocate" :disabled="locating">
                  <IconifyIcon :icon="locating ? 'lucide:loader-2' : 'lucide:locate'" :class="locating ? 'size-3.5 animate-spin' : 'size-3.5'" />
                </button>
                <button class="wx-glass-icon" @click="fetchAll" :disabled="loading">
                  <IconifyIcon :icon="loading ? 'lucide:loader-2' : 'lucide:refresh-cw'" :class="loading ? 'size-3.5 animate-spin' : 'size-3.5'" />
                </button>
              </div>
            </div>

            <!-- 主温度 -->
            <div class="wx-main__hero">
              <div class="wx-main__temp">{{ current.temperature !== null ? Math.round(current.temperature) : '--' }}°</div>
              <div class="wx-main__desc">
                <IconifyIcon :icon="`lucide:${getIcon(current.weather_code, current.is_day)}`" style="width:24px;height:24px;" />
                <span>{{ weatherText(current) }}</span>
              </div>
            </div>

            <!-- 指标卡片 -->
            <div class="wx-metrics">
              <div class="wx-metric-card">
                <IconifyIcon icon="lucide:droplets" class="size-4" style="color: #93c5fd;" />
                <span class="wx-metric-card__val">{{ current.humidity ?? '--' }}%</span>
                <span class="wx-metric-card__label">{{ $t('plugin.weather-widget.ui.humidity') }}</span>
              </div>
              <div class="wx-metric-card">
                <IconifyIcon icon="lucide:wind" class="size-4" style="color: #a5f3fc;" />
                <span class="wx-metric-card__val">{{ current.wind_speed ?? '--' }}</span>
                <span class="wx-metric-card__label">km/h</span>
              </div>
              <div class="wx-metric-card">
                <IconifyIcon icon="lucide:sun-dim" class="size-4" style="color: #fcd34d;" />
                <span class="wx-metric-card__val">{{ current.uv_index ?? '--' }}</span>
                <span class="wx-metric-card__label">UV</span>
              </div>
            </div>

            <!-- 多日预报 -->
            <div v-if="forecast.length > 0" class="wx-forecast">
              <div
                v-for="(day, index) in forecast"
                :key="day.date"
                class="wx-forecast__row"
              >
                <span class="wx-forecast__day">{{ formatDate(day.date, index) }}</span>
                <span class="wx-forecast__weekday">{{ formatWeekday(day.date) }}</span>
                <IconifyIcon :icon="`lucide:${getIcon(day.weather_code)}`" class="wx-forecast__icon" style="width:18px;height:18px;" />
                <span class="wx-forecast__range">
                  <span class="wx-forecast__hi">{{ day.temp_max !== null ? Math.round(day.temp_max) : '--' }}°</span>
                  <span class="wx-forecast__lo">{{ day.temp_min !== null ? Math.round(day.temp_min) : '--' }}°</span>
                </span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </template>
  </Popover>
</template>

<!-- 所有样式通过 setup() JS 注入（scoped CSS 在 Popover portal 中不生效） -->
