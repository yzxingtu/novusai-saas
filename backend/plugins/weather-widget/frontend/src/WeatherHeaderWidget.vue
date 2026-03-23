<script lang="ts" setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { Tooltip } from 'ant-design-vue';
import { IconifyIcon, $t } from '@novus/plugin-shared';

import type { CityInfo } from './use-weather';
import { POPULAR_CITIES, useWeather } from './use-weather';
import {
  formatCityMeta,
  formatClockTime,
  formatSunTime,
  formatTemperature,
  formatWindSpeed,
  getAqiColor,
  getAqiLevel,
  getDayLabel,
  getWeatherText,
  temperatureSymbol,
} from './weather-ui';
import { getWeatherBg, getWeatherCodeInfo } from './weather-codes';

const {
  cityName,
  recentCities,
  current,
  forecast,
  hourly,
  airQuality,
  loading,
  initialLoading,
  error,
  locating,
  locateError,
  showCitySelector,
  isStale,
  temperatureUnit,
  forecastDays,
  lastUpdatedAt,
  fetchAll,
  searchCity,
  selectCity,
  geolocate,
} = useWeather();

const popoverOpen = ref(false);
const searchKeyword = ref('');
const searchResults = ref<CityInfo[]>([]);
const searching = ref(false);
const hourlyScrollRef = ref<HTMLElement | null>(null);
const triggerRef = ref<HTMLElement | null>(null);
const panelRef = ref<HTMLElement | null>(null);
const overlayStyle = ref<Record<string, string>>({});
let searchTimer: ReturnType<typeof setTimeout> | null = null;
let overlaySyncRaf: null | number = null;

const isZh = computed(() => $t('plugin.weather-widget._meta.lang') === 'zh');
const tempUnit = computed(() => temperatureSymbol(temperatureUnit.value));
const speedUnit = computed(() =>
  temperatureUnit.value === 'fahrenheit'
    ? $t('plugin.weather-widget.ui.unit_mph')
    : $t('plugin.weather-widget.ui.unit_kmh'),
);
const todayForecast = computed(() => forecast.value[0] ?? null);
const displayForecast = computed(() => forecast.value.slice(0, Math.min(forecastDays.value, 3)));
const displayHourly = computed(() => hourly.value.slice(0, 6));
const freshnessLabel = computed(() =>
  isStale.value
    ? $t('plugin.weather-widget.ui.cached_data')
    : $t('plugin.weather-widget.ui.live_data'),
);
const updateTime = computed(() =>
  formatClockTime(lastUpdatedAt.value, isZh.value ? 'zh-CN' : 'en-US'),
);
const bgInfo = computed(() => {
  if (!current.value) {
    return { bgClass: 'wx-bg--cloudy-day', scene: 'cloud' };
  }
  return getWeatherBg(current.value.weather_code, current.value.is_day);
});
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
    },
    {
      key: 'wind',
      label: $t('plugin.weather-widget.ui.wind_speed'),
      note: undefined,
      tone: undefined,
      value: `${formatWindSpeed(current.value.wind_speed, temperatureUnit.value)} ${speedUnit.value}`,
    },
    {
      key: 'uv',
      label: $t('plugin.weather-widget.ui.uv_index'),
      note: undefined,
      tone: undefined,
      value: `${current.value.uv_index ?? '--'}`,
    },
    {
      key: 'aqi',
      label: $t('plugin.weather-widget.ui.aqi'),
      value: `${airQuality.value?.aqi ?? '--'}`,
      note: aqiLabel(airQuality.value?.aqi),
      tone: getAqiColor(airQuality.value?.aqi),
    },
  ];
});

function weatherIcon(code: number, isDay = true): string {
  return getWeatherCodeInfo(code, isDay).icon;
}

function weatherText(item: { weather_text_zh?: string; weather_text_en?: string }): string {
  return getWeatherText(item, isZh.value);
}

function formatHour(time: string, currentHour?: boolean): string {
  if (currentHour) {
    return $t('plugin.weather-widget.ui.now');
  }
  return time;
}

function aqiLabel(aqi: number | null | undefined): string {
  const level = getAqiLevel(aqi);
  return $t(`plugin.weather-widget.aqi_level.${level}`);
}

function estimatePanelWidth(): number {
  return Math.max(Math.min(360, window.innerWidth - 20), 0);
}

function updateOverlayPosition(): void {
  const trigger = triggerRef.value;
  if (!trigger || !trigger.isConnected) {
    popoverOpen.value = false;
    return;
  }
  const gap = 4;
  const margin = 10;
  const triggerRect = trigger.getBoundingClientRect();
  const panelWidth = panelRef.value?.offsetWidth ?? estimatePanelWidth();
  const viewportMaxLeft = Math.max(window.innerWidth - panelWidth - margin, margin);
  const left = Math.min(
    Math.max(triggerRect.right - panelWidth, margin),
    viewportMaxLeft,
  );
  overlayStyle.value = {
    left: `${left}px`,
    top: `${Math.max(triggerRect.bottom + gap, margin)}px`,
  };
}

function handleDocumentPointerDown(event: PointerEvent): void {
  if (!popoverOpen.value) {
    return;
  }
  const target = event.target as Node | null;
  if (!target) {
    return;
  }
  if (triggerRef.value?.contains(target) || panelRef.value?.contains(target)) {
    return;
  }
  popoverOpen.value = false;
}

function handleDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    popoverOpen.value = false;
  }
}

function startOverlaySync(): void {
  stopOverlaySync();
  const sync = () => {
    updateOverlayPosition();
    overlaySyncRaf = requestAnimationFrame(sync);
  };
  sync();
  document.addEventListener('pointerdown', handleDocumentPointerDown, true);
  window.addEventListener('keydown', handleDocumentKeydown);
}

function stopOverlaySync(): void {
  if (overlaySyncRaf != null) {
    cancelAnimationFrame(overlaySyncRaf);
    overlaySyncRaf = null;
  }
  document.removeEventListener('pointerdown', handleDocumentPointerDown, true);
  window.removeEventListener('keydown', handleDocumentKeydown);
}

function togglePopover(): void {
  popoverOpen.value = !popoverOpen.value;
}

function handleSearchInput(value: string): void {
  searchKeyword.value = value;
  if (searchTimer) {
    clearTimeout(searchTimer);
  }
  if (!value.trim()) {
    searching.value = false;
    searchResults.value = [];
    return;
  }
  searching.value = true;
  searchTimer = setTimeout(async () => {
    searchResults.value = await searchCity(value.trim());
    searching.value = false;
  }, 260);
}

async function handleCitySelect(city: CityInfo): Promise<void> {
  searchKeyword.value = '';
  searchResults.value = [];
  await selectCity(city);
}

function scrollToCurrentHour(): void {
  nextTick(() => {
    const node = hourlyScrollRef.value;
    if (!node) {
      return;
    }
    const currentItem = node.querySelector('.wx-hour-item--active') as HTMLElement | null;
    if (!currentItem) {
      return;
    }
    node.scrollTo({
      left: Math.max(currentItem.offsetLeft - 16, 0),
      behavior: 'smooth',
    });
  });
}

watch(hourly, () => {
  if (!popoverOpen.value) {
    return;
  }
  scrollToCurrentHour();
});

watch(popoverOpen, (open) => {
  if (open) {
    scrollToCurrentHour();
    nextTick(() => {
      startOverlaySync();
    });
    return;
  }
  stopOverlaySync();
});

onBeforeUnmount(() => {
  if (searchTimer) {
    clearTimeout(searchTimer);
  }
  stopOverlaySync();
});
</script>

<template>
  <Tooltip :title="$t('plugin.weather-widget.ui.open_weather')" placement="bottom">
    <button
      ref="triggerRef"
      type="button"
      class="wx-trigger"
      :aria-label="$t('plugin.weather-widget.ui.open_weather')"
      :aria-expanded="popoverOpen"
      @click="togglePopover"
    >
      <span class="wx-trigger__icon-wrap">
        <template v-if="current && !initialLoading">
          <IconifyIcon
            :icon="`lucide:${weatherIcon(current.weather_code, current.is_day)}`"
            class="wx-trigger__icon"
          />
        </template>
        <template v-else-if="initialLoading">
          <IconifyIcon icon="lucide:loader-2" class="wx-trigger__icon animate-spin" />
        </template>
        <template v-else>
          <IconifyIcon icon="lucide:cloud-off" class="wx-trigger__icon" />
        </template>
      </span>
      <span class="wx-trigger__copy">
        <small>{{ cityName }}</small>
        <strong>
          <template v-if="current && !initialLoading">
            {{ formatTemperature(current.temperature, temperatureUnit) }}°
          </template>
          <template v-else>
            --
          </template>
        </strong>
      </span>
    </button>
  </Tooltip>

  <Teleport to="body">
    <div
      v-if="popoverOpen"
      class="weather-popover-immersive-overlay"
      :style="overlayStyle"
    >
      <section
        ref="panelRef"
        class="wx-panel wx-noise"
        :class="[bgInfo.bgClass, `wx-scene--${bgInfo.scene}`]"
      >
        <div class="wx-panel__veil" />

        <Transition name="wx-fade-slide" mode="out-in">
          <div v-if="showCitySelector" key="city-selector" class="wx-city-panel">
            <header class="wx-city-panel__head">
              <button
                type="button"
                class="wx-icon-btn"
                :aria-label="$t('plugin.weather-widget.ui.back')"
                @click="showCitySelector = false"
              >
                <IconifyIcon icon="lucide:chevron-left" class="size-4" />
              </button>
              <h3>{{ $t('plugin.weather-widget.ui.change_city') }}</h3>
              <button
                type="button"
                class="wx-icon-btn"
                :aria-label="$t('plugin.weather-widget.ui.close')"
                @click="popoverOpen = false"
              >
                <IconifyIcon icon="lucide:x" class="size-4" />
              </button>
            </header>

            <div class="wx-city-panel__summary">
              <span class="wx-city-panel__label">
                {{ $t('plugin.weather-widget.ui.current_city') }}
              </span>
              <strong>{{ cityName }}</strong>
            </div>

            <label class="wx-search">
              <IconifyIcon icon="lucide:search" class="size-4 opacity-70" />
              <input
                :value="searchKeyword"
                :placeholder="$t('plugin.weather-widget.ui.search_city')"
                @input="handleSearchInput(($event.target as HTMLInputElement).value)"
              />
            </label>

            <div class="wx-city-list">
              <div v-if="searchKeyword.trim()">
                <div v-if="searching" class="wx-state-line">
                  <IconifyIcon icon="lucide:loader-2" class="size-4 animate-spin" />
                  {{ $t('plugin.weather-widget.ui.loading') }}
                </div>
                <button
                  v-for="city in searchResults"
                  :key="`search-${city.latitude}-${city.longitude}`"
                  type="button"
                  class="wx-city-chip"
                  @click="handleCitySelect(city)"
                >
                  <span class="wx-city-chip__main">
                    <IconifyIcon icon="lucide:map-pin" class="size-3.5 opacity-65" />
                    <span class="truncate">{{ city.name }}</span>
                  </span>
                  <span
                    v-if="formatCityMeta(city)"
                    class="wx-city-chip__meta"
                  >
                    {{ formatCityMeta(city) }}
                  </span>
                </button>
                <div v-if="!searching && searchResults.length === 0" class="wx-state-line">
                  {{ $t('plugin.weather-widget.error.city_not_found') }}
                </div>
              </div>

              <button
                type="button"
                class="wx-locate-btn"
                :disabled="locating"
                :aria-label="$t('plugin.weather-widget.ui.auto_locate')"
                @click="geolocate"
              >
                <IconifyIcon
                  :icon="locating ? 'lucide:loader-2' : 'lucide:locate'"
                  :class="locating ? 'size-4 animate-spin' : 'size-4'"
                />
                {{ locating ? $t('plugin.weather-widget.ui.locating') : $t('plugin.weather-widget.ui.auto_locate') }}
              </button>
              <div v-if="locateError" class="wx-state-line wx-state-line--error">
                {{ $t(`plugin.weather-widget.error.${locateError}`) }}
              </div>

              <div v-if="recentCities.length > 0" class="wx-city-group">
                <h4>{{ $t('plugin.weather-widget.ui.recent_cities') }}</h4>
                <div class="wx-city-grid">
                  <button
                    v-for="city in recentCities"
                    :key="`recent-${city.latitude}-${city.longitude}`"
                    type="button"
                    class="wx-city-chip"
                    @click="handleCitySelect(city)"
                  >
                    <span class="truncate">{{ city.name }}</span>
                  </button>
                </div>
              </div>

              <div class="wx-city-group">
                <h4>{{ $t('plugin.weather-widget.ui.popular_cities') }}</h4>
                <div class="wx-city-grid">
                  <button
                    v-for="city in POPULAR_CITIES"
                    :key="`popular-${city.latitude}-${city.longitude}`"
                    type="button"
                    class="wx-city-chip"
                    @click="handleCitySelect(city)"
                  >
                    <span class="truncate">{{ city.name }}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-else key="weather-main" class="wx-main-panel">
            <template v-if="initialLoading && !current">
              <div class="wx-skeleton-wrap">
                <div class="wx-skeleton wx-skeleton--lg" />
                <div class="wx-skeleton wx-skeleton--md" />
                <div class="wx-skeleton wx-skeleton--grid" />
              </div>
            </template>

            <template v-else-if="error && !current">
              <div class="wx-empty">
                <IconifyIcon icon="lucide:cloud-off" class="size-10 opacity-65" />
                <p>{{ $t('plugin.weather-widget.ui.error') }}</p>
                <button type="button" class="wx-action-btn" @click="fetchAll">
                  <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
                  {{ $t('plugin.weather-widget.ui.retry') }}
                </button>
              </div>
            </template>

            <template v-else-if="current">
              <header class="wx-main-head">
                <button
                  type="button"
                  class="wx-city-btn"
                  :aria-label="$t('plugin.weather-widget.ui.change_city')"
                  @click="showCitySelector = true"
                >
                  <IconifyIcon icon="lucide:map-pin" class="size-3.5 opacity-70" />
                  <span class="truncate">{{ cityName }}</span>
                  <IconifyIcon icon="lucide:chevron-down" class="size-3.5 opacity-60" />
                </button>
                <div class="wx-head-actions">
                  <span class="wx-status-chip">{{ freshnessLabel }}</span>
                  <button
                    type="button"
                    class="wx-icon-btn"
                    :disabled="locating"
                    :aria-label="$t('plugin.weather-widget.ui.auto_locate')"
                    @click="geolocate"
                  >
                    <IconifyIcon
                      :icon="locating ? 'lucide:loader-2' : 'lucide:locate'"
                      :class="locating ? 'size-4 animate-spin' : 'size-4'"
                    />
                  </button>
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
              </header>

              <div class="wx-scene" aria-hidden="true">
                <span class="wx-scene__orb" />
                <span class="wx-scene__cloud wx-scene__cloud--1" />
                <span class="wx-scene__cloud wx-scene__cloud--2" />
                <span class="wx-scene__spark wx-scene__spark--1" />
                <span class="wx-scene__spark wx-scene__spark--2" />
                <span class="wx-scene__spark wx-scene__spark--3" />
                <span class="wx-scene__drop wx-scene__drop--1" />
                <span class="wx-scene__drop wx-scene__drop--2" />
                <span class="wx-scene__drop wx-scene__drop--3" />
                <span class="wx-scene__flake wx-scene__flake--1" />
                <span class="wx-scene__flake wx-scene__flake--2" />
                <span class="wx-scene__mist wx-scene__mist--1" />
                <span class="wx-scene__mist wx-scene__mist--2" />
                <span class="wx-scene__flash" />
              </div>

              <div class="wx-hero">
                <div class="wx-hero__eyebrow">
                  <span>{{ freshnessLabel }}</span>
                  <span>{{ $t('plugin.weather-widget.ui.last_updated') }} {{ updateTime }}</span>
                </div>
                <div class="wx-hero__body">
                  <div class="wx-hero__copy">
                    <div class="wx-hero__temp">
                      {{ formatTemperature(current.temperature, temperatureUnit) }}°
                    </div>
                    <div class="wx-hero__text">{{ weatherText(current) }}</div>
                    <div class="wx-hero__sub">
                      <span>
                        {{ $t('plugin.weather-widget.ui.feels_like') }}
                        {{ formatTemperature(current.apparent_temperature, temperatureUnit) }}°{{ tempUnit }}
                      </span>
                      <span v-if="todayForecast">
                        {{ $t('plugin.weather-widget.ui.high_short') }}
                        {{ formatTemperature(todayForecast.temp_max, temperatureUnit) }}°
                        /
                        {{ $t('plugin.weather-widget.ui.low_short') }}
                        {{ formatTemperature(todayForecast.temp_min, temperatureUnit) }}°
                      </span>
                    </div>
                  </div>
                  <div class="wx-hero__meta">
                    <div class="wx-hero__icon-shell">
                      <IconifyIcon
                        :icon="`lucide:${weatherIcon(current.weather_code, current.is_day)}`"
                        class="wx-hero__icon"
                      />
                    </div>
                    <span class="wx-hero__unit">{{ tempUnit }}</span>
                  </div>
                </div>
                <div v-if="isStale" class="wx-stale-badge">
                  {{ $t('plugin.weather-widget.ui.data_stale') }}
                </div>
              </div>

              <section class="wx-chip-grid">
                <article
                  v-for="metric in quickMetrics"
                  :key="metric.key"
                  class="wx-chip"
                >
                  <span>{{ metric.label }}</span>
                  <strong :style="metric.tone ? { color: metric.tone } : undefined">
                    {{ metric.value }}
                  </strong>
                  <small v-if="metric.note" :style="metric.tone ? { color: metric.tone } : undefined">
                    {{ metric.note }}
                  </small>
                </article>
              </section>

              <section v-if="displayHourly.length > 0" class="wx-hourly-band">
                <div class="wx-section-head wx-section-head--inline">
                  <h4>{{ $t('plugin.weather-widget.ui.hourly_forecast') }}</h4>
                  <span>{{ $t('plugin.weather-widget.ui.hourly_digest') }}</span>
                </div>
                <div ref="hourlyScrollRef" class="wx-hourly-scroll">
                  <article
                    v-for="(item, index) in displayHourly"
                    :key="`hour-${index}`"
                    class="wx-hour-item"
                    :class="item.is_current ? 'wx-hour-item--active' : ''"
                  >
                    <span class="wx-hour-item__time">{{ formatHour(item.time, item.is_current) }}</span>
                    <IconifyIcon
                      :icon="`lucide:${weatherIcon(item.weather_code, current.is_day)}`"
                      class="size-4"
                    />
                    <span class="wx-hour-item__temp">
                      {{ formatTemperature(item.temperature, temperatureUnit) }}°
                    </span>
                  </article>
                </div>
              </section>

              <div class="wx-sun-strip">
                <article class="wx-sun-chip">
                  <span>{{ $t('plugin.weather-widget.ui.sunrise') }}</span>
                  <strong>{{ formatSunTime(todayForecast?.sunrise) }}</strong>
                </article>
                <article class="wx-sun-chip">
                  <span>{{ $t('plugin.weather-widget.ui.sunset') }}</span>
                  <strong>{{ formatSunTime(todayForecast?.sunset) }}</strong>
                </article>
              </div>

              <section v-if="displayForecast.length > 0" class="wx-forecast-sheet">
                <div class="wx-section-head wx-section-head--inline">
                  <h4>{{ $t('plugin.weather-widget.ui.forecast') }}</h4>
                  <span>{{ $t('plugin.weather-widget.ui.forecast_digest') }}</span>
                </div>
                <article
                  v-for="(day, index) in displayForecast"
                  :key="day.date"
                  class="wx-forecast-row"
                >
                  <div class="wx-forecast-row__day">
                    <span>{{ getDayLabel(day.date, index, $t) }}</span>
                    <small>{{ weatherText(day) }}</small>
                  </div>
                  <IconifyIcon :icon="`lucide:${weatherIcon(day.weather_code, current.is_day)}`" class="size-4" />
                  <div class="wx-forecast-row__temp">
                    <span>
                      {{ $t('plugin.weather-widget.ui.high_short') }}
                      {{ formatTemperature(day.temp_max, temperatureUnit) }}°
                    </span>
                    <span>
                      {{ $t('plugin.weather-widget.ui.low_short') }}
                      {{ formatTemperature(day.temp_min, temperatureUnit) }}°
                    </span>
                  </div>
                </article>
              </section>
            </template>
          </div>
        </Transition>
      </section>
    </div>
  </Teleport>
</template>
