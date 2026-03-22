<script lang="ts" setup>
import { computed } from 'vue';

import { $t, IconifyIcon } from '@novus/plugin-shared';

import { useWeather } from './use-weather';
import { getWeatherBg, getWeatherCodeInfo } from './weather-codes';

const {
  cityName,
  current,
  forecast,
  airQuality,
  loading,
  initialLoading,
  error,
  isStale,
  fetchAll,
} = useWeather();

const previewDays = computed(() => forecast.value.slice(0, 3));

const bgInfo = computed(() => {
  if (!current.value) {
    return { bgClass: 'wx-bg--cloudy-day' };
  }
  return getWeatherBg(current.value.weather_code, current.value.is_day);
});

const isZh = computed(() => $t('plugin.weather-widget._meta.lang') === 'zh');

function weatherText(item: {
  weather_text_en?: string;
  weather_text_zh?: string;
}): string {
  return isZh.value
    ? (item.weather_text_zh || item.weather_text_en || '')
    : (item.weather_text_en || item.weather_text_zh || '');
}

function weatherIcon(code: number, isDay = true): string {
  return getWeatherCodeInfo(code, isDay).icon;
}

function formatDayLabel(dateStr: string, index: number): string {
  if (index === 0) return $t('plugin.weather-widget.ui.today');
  if (index === 1) return $t('plugin.weather-widget.ui.tomorrow');
  const dayIndex = new Date(dateStr).getDay();
  return $t(`plugin.weather-widget.ui.weekday_${dayIndex}`);
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
  if (aqi == null) return 'rgba(255,255,255,0.82)';
  if (aqi <= 50) return '#bbf7d0';
  if (aqi <= 100) return '#fde68a';
  if (aqi <= 150) return '#fdba74';
  if (aqi <= 200) return '#fca5a5';
  if (aqi <= 300) return '#ddd6fe';
  return '#fecdd3';
}
</script>

<template>
  <div class="flex h-full flex-col gap-3" style="min-height: 280px">
    <div
      v-if="current"
      class="wx-noise relative overflow-hidden rounded-2xl p-4 text-white shadow-sm"
      :class="bgInfo.bgClass"
    >
      <div class="wx-panel-inner-glow" />
      <div class="relative flex items-start justify-between gap-3" style="z-index: 1">
        <div class="min-w-0">
          <div
            class="truncate text-xs uppercase"
            style="color: rgba(255, 255, 255, 0.65); letter-spacing: 0.24em"
          >
            {{ cityName }}
          </div>
          <div class="mt-3 flex items-end gap-3">
            <span class="text-5xl font-extralight leading-none">
              {{ current.temperature !== null ? Math.round(current.temperature) : '--' }}°
            </span>
            <div class="pb-1">
              <div class="text-sm font-medium" style="color: rgba(255, 255, 255, 0.95)">
                {{ weatherText(current) }}
              </div>
              <div
                class="mt-1 text-xs"
                style="color: rgba(255, 255, 255, 0.7)"
              >
                {{ isStale ? $t('plugin.weather-widget.ui.data_stale') : $t('plugin.weather-widget.ui.temperature') }}
              </div>
            </div>
          </div>
        </div>
        <div class="flex items-start gap-2">
          <IconifyIcon
            :icon="`lucide:${weatherIcon(current.weather_code, current.is_day)}`"
            class="size-10 shrink-0 text-white/90"
          />
          <button
            class="flex size-9 items-center justify-center rounded-full border border-white/15 bg-white/10 text-white transition-colors hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="loading"
            @click="fetchAll"
          >
            <IconifyIcon
              :icon="loading ? 'lucide:loader-2' : 'lucide:refresh-cw'"
              :class="loading ? 'size-4 animate-spin' : 'size-4'"
            />
          </button>
        </div>
      </div>

      <div class="relative mt-4 grid grid-cols-3 gap-2" style="z-index: 1">
        <div
          class="rounded-2xl border px-3 py-2.5 backdrop-blur-sm"
          style="background: rgba(255, 255, 255, 0.1); border-color: rgba(255, 255, 255, 0.1)"
        >
          <div class="text-xs" style="color: rgba(255, 255, 255, 0.6)">
            {{ $t('plugin.weather-widget.ui.humidity') }}
          </div>
          <div class="mt-1 text-sm font-semibold tabular-nums">
            {{ current.humidity ?? '--' }}%
          </div>
        </div>
        <div
          class="rounded-2xl border px-3 py-2.5 backdrop-blur-sm"
          style="background: rgba(255, 255, 255, 0.1); border-color: rgba(255, 255, 255, 0.1)"
        >
          <div class="text-xs" style="color: rgba(255, 255, 255, 0.6)">
            {{ $t('plugin.weather-widget.ui.wind_speed') }}
          </div>
          <div class="mt-1 text-sm font-semibold tabular-nums">
            {{ current.wind_speed ?? '--' }} km/h
          </div>
        </div>
        <div
          class="rounded-2xl border px-3 py-2.5 backdrop-blur-sm"
          style="background: rgba(255, 255, 255, 0.1); border-color: rgba(255, 255, 255, 0.1)"
        >
          <div class="text-xs" style="color: rgba(255, 255, 255, 0.6)">
            {{ $t('plugin.weather-widget.ui.aqi') }}
          </div>
          <div class="mt-1 text-sm font-semibold tabular-nums">
            {{ airQuality?.aqi ?? '--' }}
          </div>
          <div
            class="mt-1 truncate text-xs"
            :style="{ color: aqiColor(airQuality?.aqi) }"
          >
            {{ aqiLevel(airQuality?.aqi) }}
          </div>
        </div>
      </div>
    </div>

    <div
      v-else-if="initialLoading"
      class="grid gap-3 sm:grid-cols-3"
    >
      <div class="wx-skeleton rounded-2xl sm:col-span-3" style="height: 168px" />
      <div
        v-for="index in 3"
        :key="index"
        class="wx-skeleton rounded-2xl"
        style="height: 102px"
      />
    </div>

    <div
      v-else
      class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-muted px-5 py-8 text-center"
      style="min-height: 220px"
    >
      <IconifyIcon icon="lucide:cloud-off" class="size-10 text-muted-foreground" />
      <div class="mt-3 text-sm font-medium text-foreground">
        {{ $t('plugin.weather-widget.ui.error') }}
      </div>
      <div
        v-if="error"
        class="mt-2 break-words text-xs leading-5 text-muted-foreground"
      >
        {{ error }}
      </div>
      <button
        class="mt-4 inline-flex items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm text-foreground transition-colors hover:bg-accent"
        @click="fetchAll"
      >
        <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
        {{ $t('plugin.weather-widget.ui.retry') }}
      </button>
    </div>

    <div
      v-if="current && previewDays.length > 0"
      class="grid gap-3 sm:grid-cols-3"
    >
      <div
        v-for="(day, index) in previewDays"
        :key="day.date"
        class="rounded-2xl border border-border bg-background p-3 shadow-sm"
      >
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0">
            <div class="text-sm font-medium text-foreground">
              {{ formatDayLabel(day.date, index) }}
            </div>
            <div class="mt-1 truncate text-xs text-muted-foreground">
              {{ weatherText(day) }}
            </div>
          </div>
          <IconifyIcon
            :icon="`lucide:${weatherIcon(day.weather_code, current.is_day)}`"
            class="size-5 shrink-0 text-primary"
          />
        </div>
        <div class="mt-4 flex items-end justify-between gap-3">
          <div class="text-2xl font-light leading-none text-foreground">
            {{ day.temp_max !== null ? Math.round(day.temp_max) : '--' }}°
          </div>
          <div class="text-sm text-muted-foreground">
            {{ day.temp_min !== null ? Math.round(day.temp_min) : '--' }}°
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
