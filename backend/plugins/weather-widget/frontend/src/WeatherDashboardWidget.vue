<script lang="ts" setup>
import { computed } from 'vue';

import { $t, IconifyIcon } from '@novus/plugin-shared';

import { useWeather } from './use-weather';
import {
  formatClockTime,
  formatTemperature,
  formatWindSpeed,
  getAqiColor,
  getAqiLevel,
  getDayLabel,
  getWeatherText,
} from './weather-ui';
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
  lastUpdatedAt,
  temperatureUnit,
  fetchAll,
} = useWeather();

const isZh = computed(() => $t('plugin.weather-widget._meta.lang') === 'zh');
const previewDays = computed(() => forecast.value.slice(0, 3));
const bgInfo = computed(() => {
  if (!current.value) {
    return { bgClass: 'wx-bg--cloudy-day', scene: 'cloud' as const };
  }
  return getWeatherBg(current.value.weather_code, current.value.is_day);
});
const updateTime = computed(() =>
  formatClockTime(lastUpdatedAt.value, isZh.value ? 'zh-CN' : 'en-US'),
);
const freshnessLabel = computed(() =>
  isStale.value
    ? $t('plugin.weather-widget.ui.cached_data')
    : $t('plugin.weather-widget.ui.live_data'),
);
const windUnitLabel = computed(() =>
  temperatureUnit.value === 'fahrenheit'
    ? $t('plugin.weather-widget.ui.unit_mph')
    : $t('plugin.weather-widget.ui.unit_kmh'),
);

const quickMetrics = computed(() => {
  if (!current.value) {
    return [];
  }

  return [
    {
      key: 'humidity',
      label: $t('plugin.weather-widget.ui.humidity'),
      note: undefined,
      tone: undefined,
      value: `${current.value.humidity ?? '--'}%`,
      wide: false,
    },
    {
      key: 'wind',
      label: $t('plugin.weather-widget.ui.wind_speed'),
      note: undefined,
      tone: undefined,
      value: `${formatWindSpeed(current.value.wind_speed, temperatureUnit.value)} ${windUnitLabel.value}`,
      wide: false,
    },
    {
      key: 'aqi',
      label: $t('plugin.weather-widget.ui.aqi'),
      value: `${airQuality.value?.aqi ?? '--'}`,
      note: $t(`plugin.weather-widget.aqi_level.${getAqiLevel(airQuality.value?.aqi)}`),
      tone: getAqiColor(airQuality.value?.aqi),
      wide: true,
    },
  ];
});

function weatherText(item: {
  weather_text_en?: string;
  weather_text_zh?: string;
}): string {
  return getWeatherText(item, isZh.value);
}

function weatherIcon(code: number, isDay = true): string {
  return getWeatherCodeInfo(code, isDay).icon;
}
</script>

<template>
  <div class="wx-dashboard-shell">
    <template v-if="current">
      <section class="wx-dashboard wx-noise" :class="[bgInfo.bgClass, `wx-scene--${bgInfo.scene}`]">
        <div class="wx-panel__veil wx-panel__veil--dashboard" />
        <div class="wx-scene wx-scene--dashboard" aria-hidden="true">
          <span class="wx-scene__orb" />
          <span class="wx-scene__cloud wx-scene__cloud--1" />
          <span class="wx-scene__cloud wx-scene__cloud--2" />
          <span class="wx-scene__spark wx-scene__spark--1" />
          <span class="wx-scene__spark wx-scene__spark--2" />
          <span class="wx-scene__drop wx-scene__drop--1" />
          <span class="wx-scene__drop wx-scene__drop--2" />
          <span class="wx-scene__flake wx-scene__flake--1" />
          <span class="wx-scene__mist wx-scene__mist--1" />
          <span class="wx-scene__flash" />
        </div>

        <div class="wx-dashboard__topbar">
          <div class="wx-dashboard__eyebrow">
            <span>{{ cityName }}</span>
            <span>{{ freshnessLabel }}</span>
          </div>
          <button
            type="button"
            class="wx-icon-btn"
            :disabled="loading"
            :aria-label="$t('plugin.weather-widget.ui.refresh')"
            @click="fetchAll"
          >
            <IconifyIcon
              :icon="loading ? 'lucide:loader-2' : 'lucide:refresh-cw'"
              :class="loading ? 'size-4 animate-spin' : 'size-4'"
            />
          </button>
        </div>

        <div class="wx-dashboard__hero">
          <div class="wx-dashboard__hero-main">
            <div class="wx-dashboard__temp">
              {{ formatTemperature(current.temperature, temperatureUnit) }}°
            </div>
            <div class="wx-dashboard__condition-wrap">
              <div class="wx-dashboard__condition-line">
                <div class="wx-dashboard__icon-wrap">
                  <IconifyIcon
                    :icon="`lucide:${weatherIcon(current.weather_code, current.is_day)}`"
                    class="wx-dashboard__icon"
                  />
                </div>
                <div class="wx-dashboard__condition">
                  {{ weatherText(current) }}
                </div>
              </div>
              <div class="wx-dashboard__meta">
                <span>
                  {{ $t('plugin.weather-widget.ui.feels_like') }}
                  {{ formatTemperature(current.apparent_temperature, temperatureUnit) }}°
                </span>
                <span>{{ $t('plugin.weather-widget.ui.last_updated') }} {{ updateTime }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="wx-dashboard__chip-row">
          <article
            v-for="metric in quickMetrics"
            :key="metric.key"
            class="wx-dashboard__chip"
            :class="metric.wide ? 'wx-dashboard__chip--wide' : ''"
          >
            <span>{{ metric.label }}</span>
            <strong :style="metric.tone ? { color: metric.tone } : undefined">
              {{ metric.value }}
            </strong>
            <small v-if="metric.note" :style="metric.tone ? { color: metric.tone } : undefined">
              {{ metric.note }}
            </small>
          </article>
        </div>

        <div v-if="previewDays.length > 0" class="wx-dashboard__forecast-ribbon">
          <article
            v-for="(day, index) in previewDays"
            :key="day.date"
            class="wx-dashboard__forecast-pill"
          >
            <div class="wx-dashboard__forecast-head">
              <span>{{ getDayLabel(day.date, index, $t) }}</span>
              <IconifyIcon
                :icon="`lucide:${weatherIcon(day.weather_code, true)}`"
                class="size-4"
              />
            </div>
            <div class="wx-dashboard__forecast-range">
              <span>{{ formatTemperature(day.temp_max, temperatureUnit) }}°</span>
              <span>{{ formatTemperature(day.temp_min, temperatureUnit) }}°</span>
            </div>
            <div class="wx-dashboard__forecast-text">{{ weatherText(day) }}</div>
          </article>
        </div>
      </section>
    </template>

    <div v-else-if="initialLoading" class="wx-dashboard-skeleton">
      <div class="wx-skeleton wx-skeleton--lg" />
      <div class="wx-dashboard-skeleton__row">
        <div class="wx-skeleton wx-skeleton--tile" />
        <div class="wx-skeleton wx-skeleton--tile" />
        <div class="wx-skeleton wx-skeleton--tile" />
      </div>
      <div class="wx-dashboard-skeleton__row">
        <div class="wx-skeleton wx-skeleton--tile" />
        <div class="wx-skeleton wx-skeleton--tile" />
        <div class="wx-skeleton wx-skeleton--tile" />
      </div>
    </div>

    <div v-else class="wx-dashboard-empty">
      <IconifyIcon icon="lucide:cloud-off" class="size-10 text-muted-foreground" />
      <div class="wx-dashboard-empty__title">
        {{ $t('plugin.weather-widget.ui.error') }}
      </div>
      <div v-if="error" class="wx-dashboard-empty__desc">
        {{ error }}
      </div>
      <button type="button" class="wx-action-btn" @click="fetchAll">
        <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
        {{ $t('plugin.weather-widget.ui.retry') }}
      </button>
    </div>
  </div>
</template>
