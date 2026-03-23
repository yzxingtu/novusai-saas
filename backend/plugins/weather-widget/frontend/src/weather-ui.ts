import type { TemperatureUnit } from './use-weather';

interface WeatherTextSource {
  weather_text_zh?: string;
  weather_text_en?: string;
}

export function getWeatherText(source: WeatherTextSource, isZh: boolean): string {
  if (isZh) {
    return source.weather_text_zh || source.weather_text_en || '--';
  }
  return source.weather_text_en || source.weather_text_zh || '--';
}

export function convertTemperature(value: number | null | undefined, unit: TemperatureUnit): number | null {
  if (value == null || Number.isNaN(value)) {
    return null;
  }
  if (unit === 'fahrenheit') {
    return (value * 9) / 5 + 32;
  }
  return value;
}

export function formatTemperature(
  value: number | null | undefined,
  unit: TemperatureUnit,
  digits = 0,
): string {
  const converted = convertTemperature(value, unit);
  if (converted == null) {
    return '--';
  }
  return converted.toFixed(digits);
}

export function temperatureSymbol(unit: TemperatureUnit): string {
  return unit === 'fahrenheit' ? 'F' : 'C';
}

export function formatWindSpeed(
  value: number | null | undefined,
  unit: TemperatureUnit,
  digits = 1,
): string {
  if (value == null || Number.isNaN(value)) {
    return '--';
  }
  const converted = unit === 'fahrenheit' ? value * 0.621371 : value;
  return converted.toFixed(digits);
}

export function windSpeedUnit(unit: TemperatureUnit): 'km/h' | 'mph' {
  return unit === 'fahrenheit' ? 'mph' : 'km/h';
}

export function formatCityMeta(city: {
  admin1?: string;
  country?: string;
}): string {
  return [city.admin1, city.country].filter(Boolean).join(' · ');
}

export function formatClockTime(
  value: number | null | undefined,
  locale: string,
): string {
  if (!value) {
    return '--:--';
  }
  return new Intl.DateTimeFormat(locale, {
    hour: '2-digit',
    minute: '2-digit',
  }).format(value);
}

export function formatSunTime(value: string | null | undefined): string {
  if (!value) {
    return '--:--';
  }
  const source = value.includes('T') ? value.split('T')[1] : value;
  if (!source) {
    return '--:--';
  }
  return source.slice(0, 5);
}

export function getAqiLevel(aqi: number | null | undefined): string {
  if (aqi == null) {
    return 'na';
  }
  if (aqi <= 50) {
    return 'good';
  }
  if (aqi <= 100) {
    return 'moderate';
  }
  if (aqi <= 150) {
    return 'unhealthy_sensitive';
  }
  if (aqi <= 200) {
    return 'unhealthy';
  }
  if (aqi <= 300) {
    return 'very_unhealthy';
  }
  return 'hazardous';
}

export function getAqiColor(aqi: number | null | undefined): string {
  if (aqi == null) {
    return '#A7B3CC';
  }
  if (aqi <= 50) {
    return '#47D16D';
  }
  if (aqi <= 100) {
    return '#EABD43';
  }
  if (aqi <= 150) {
    return '#F49D58';
  }
  if (aqi <= 200) {
    return '#F06B67';
  }
  if (aqi <= 300) {
    return '#A47DE8';
  }
  return '#D45A8A';
}

export function getDayLabel(dateStr: string, index: number, t: (key: string) => string): string {
  if (index === 0) {
    return t('plugin.weather-widget.ui.today');
  }
  if (index === 1) {
    return t('plugin.weather-widget.ui.tomorrow');
  }
  if (index === 2) {
    return t('plugin.weather-widget.ui.day_after');
  }
  const dayIndex = new Date(dateStr).getDay();
  return t(`plugin.weather-widget.ui.weekday_${dayIndex}`);
}
