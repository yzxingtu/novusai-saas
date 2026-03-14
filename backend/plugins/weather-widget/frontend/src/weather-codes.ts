/**
 * WMO Weather Code 映射
 *
 * 将 Open-Meteo 返回的 WMO weather_code 映射到 Lucide 图标名和场景类型。
 */

export interface WeatherCodeInfo {
  icon: string;
  nightIcon?: string;
  scene: 'clear' | 'cloudy' | 'fog' | 'drizzle' | 'rain' | 'snow' | 'thunderstorm';
}

const WMO_MAP: Record<number, WeatherCodeInfo> = {
  0:  { icon: 'sun', nightIcon: 'moon', scene: 'clear' },
  1:  { icon: 'sun', nightIcon: 'moon', scene: 'clear' },
  2:  { icon: 'cloud-sun', nightIcon: 'cloud-moon', scene: 'cloudy' },
  3:  { icon: 'cloud', scene: 'cloudy' },
  45: { icon: 'cloud-fog', scene: 'fog' },
  48: { icon: 'cloud-fog', scene: 'fog' },
  51: { icon: 'cloud-drizzle', scene: 'drizzle' },
  53: { icon: 'cloud-drizzle', scene: 'drizzle' },
  55: { icon: 'cloud-drizzle', scene: 'drizzle' },
  56: { icon: 'cloud-drizzle', scene: 'drizzle' },
  57: { icon: 'cloud-drizzle', scene: 'drizzle' },
  61: { icon: 'cloud-rain', scene: 'rain' },
  63: { icon: 'cloud-rain', scene: 'rain' },
  65: { icon: 'cloud-rain', scene: 'rain' },
  66: { icon: 'cloud-rain', scene: 'rain' },
  67: { icon: 'cloud-rain', scene: 'rain' },
  71: { icon: 'snowflake', scene: 'snow' },
  73: { icon: 'snowflake', scene: 'snow' },
  75: { icon: 'snowflake', scene: 'snow' },
  77: { icon: 'snowflake', scene: 'snow' },
  80: { icon: 'cloud-rain', scene: 'rain' },
  81: { icon: 'cloud-rain', scene: 'rain' },
  82: { icon: 'cloud-rain', scene: 'rain' },
  85: { icon: 'snowflake', scene: 'snow' },
  86: { icon: 'snowflake', scene: 'snow' },
  95: { icon: 'cloud-lightning', scene: 'thunderstorm' },
  96: { icon: 'cloud-lightning', scene: 'thunderstorm' },
  99: { icon: 'cloud-lightning', scene: 'thunderstorm' },
};

const DEFAULT_INFO: WeatherCodeInfo = {
  icon: 'cloud',
  scene: 'cloudy',
};

export function getWeatherCodeInfo(
  code: number,
  isDay = true,
): { icon: string; scene: WeatherCodeInfo['scene'] } {
  const info = WMO_MAP[code] ?? DEFAULT_INFO;
  const icon = !isDay && info.nightIcon ? info.nightIcon : info.icon;
  return { icon, scene: info.scene };
}

/**
 * 背景渐变映射：场景 + 日夜 -> CSS class
 */
export interface WeatherBgInfo {
  bgClass: string;
  scene: 'sun' | 'moon-star' | 'cloud' | 'rain' | 'snow' | 'thunder' | 'fog' | 'none';
}

const BG_MAP: Record<string, WeatherBgInfo> = {
  'clear-day':          { bgClass: 'wx-bg--clear-day',    scene: 'sun' },
  'clear-night':        { bgClass: 'wx-bg--clear-night',  scene: 'moon-star' },
  'cloudy-day':         { bgClass: 'wx-bg--cloudy-day',   scene: 'cloud' },
  'cloudy-night':       { bgClass: 'wx-bg--cloudy-night', scene: 'cloud' },
  'fog-day':            { bgClass: 'wx-bg--fog',          scene: 'fog' },
  'fog-night':          { bgClass: 'wx-bg--fog',          scene: 'fog' },
  'drizzle-day':        { bgClass: 'wx-bg--rain-day',     scene: 'rain' },
  'drizzle-night':      { bgClass: 'wx-bg--rain-night',   scene: 'rain' },
  'rain-day':           { bgClass: 'wx-bg--rain-day',     scene: 'rain' },
  'rain-night':         { bgClass: 'wx-bg--rain-night',   scene: 'rain' },
  'snow-day':           { bgClass: 'wx-bg--snow-day',     scene: 'snow' },
  'snow-night':         { bgClass: 'wx-bg--snow-night',   scene: 'snow' },
  'thunderstorm-day':   { bgClass: 'wx-bg--thunder',      scene: 'thunder' },
  'thunderstorm-night': { bgClass: 'wx-bg--thunder',      scene: 'thunder' },
};

export function getWeatherBg(code: number, isDay = true): WeatherBgInfo {
  const info = WMO_MAP[code] ?? DEFAULT_INFO;
  const suffix = isDay ? 'day' : 'night';
  const key = `${info.scene}-${suffix}`;
  return BG_MAP[key] ?? { bgClass: 'wx-bg--cloudy-day', scene: 'cloud' };
}
