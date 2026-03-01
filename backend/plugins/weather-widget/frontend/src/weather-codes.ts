/**
 * WMO Weather Code 映射
 *
 * 将 Open-Meteo 返回的 WMO weather_code 映射到 Lucide 图标名和描述。
 * 与后端 open_meteo.py 中的 WMO_CODES 保持一致。
 */

export interface WeatherCodeInfo {
  /** Lucide 图标名（不含 lucide: 前缀） */
  icon: string;
  /** 夜间图标（可选，未指定则使用 icon） */
  nightIcon?: string;
  /** 动画类型，用于 WeatherAnimation 组件 */
  animation: 'clear' | 'cloudy' | 'drizzle' | 'fog' | 'rain' | 'snow' | 'thunderstorm';
}

const WMO_MAP: Record<number, WeatherCodeInfo> = {
  0: { icon: 'sun', nightIcon: 'moon', animation: 'clear' },
  1: { icon: 'sun', nightIcon: 'moon', animation: 'clear' },
  2: { icon: 'cloud-sun', nightIcon: 'cloud-moon', animation: 'cloudy' },
  3: { icon: 'cloud', animation: 'cloudy' },
  45: { icon: 'cloud-fog', animation: 'fog' },
  48: { icon: 'cloud-fog', animation: 'fog' },
  51: { icon: 'cloud-drizzle', animation: 'drizzle' },
  53: { icon: 'cloud-drizzle', animation: 'drizzle' },
  55: { icon: 'cloud-drizzle', animation: 'drizzle' },
  56: { icon: 'cloud-drizzle', animation: 'drizzle' },
  57: { icon: 'cloud-drizzle', animation: 'drizzle' },
  61: { icon: 'cloud-rain', animation: 'rain' },
  63: { icon: 'cloud-rain', animation: 'rain' },
  65: { icon: 'cloud-rain', animation: 'rain' },
  66: { icon: 'cloud-rain', animation: 'rain' },
  67: { icon: 'cloud-rain', animation: 'rain' },
  71: { icon: 'snowflake', animation: 'snow' },
  73: { icon: 'snowflake', animation: 'snow' },
  75: { icon: 'snowflake', animation: 'snow' },
  77: { icon: 'snowflake', animation: 'snow' },
  80: { icon: 'cloud-rain', animation: 'rain' },
  81: { icon: 'cloud-rain', animation: 'rain' },
  82: { icon: 'cloud-rain', animation: 'rain' },
  85: { icon: 'snowflake', animation: 'snow' },
  86: { icon: 'snowflake', animation: 'snow' },
  95: { icon: 'cloud-lightning', animation: 'thunderstorm' },
  96: { icon: 'cloud-lightning', animation: 'thunderstorm' },
  99: { icon: 'cloud-lightning', animation: 'thunderstorm' },
};

const DEFAULT_INFO: WeatherCodeInfo = {
  icon: 'cloud',
  animation: 'cloudy',
};

/**
 * 根据 WMO weather code 获取图标和动画信息
 */
export function getWeatherCodeInfo(
  code: number,
  isDay = true,
): { icon: string; animation: WeatherCodeInfo['animation'] } {
  const info = WMO_MAP[code] ?? DEFAULT_INFO;
  const icon = !isDay && info.nightIcon ? info.nightIcon : info.icon;
  return { icon, animation: info.animation };
}

/**
 * 沉浸式背景映射：WMO code → CSS class + 粒子类型
 */
export interface WeatherBgInfo {
  bgClass: string;
  particles: 'none' | 'rain' | 'snow' | 'cloud';
}

const BG_MAP: Record<string, WeatherBgInfo> = {
  'clear-day':   { bgClass: 'wx-bg--clear-day',   particles: 'none' },
  'clear-night': { bgClass: 'wx-bg--clear-night',  particles: 'none' },
  'cloudy-day':  { bgClass: 'wx-bg--cloudy-day',   particles: 'cloud' },
  'cloudy-night': { bgClass: 'wx-bg--cloudy-night', particles: 'cloud' },
  'fog-day':     { bgClass: 'wx-bg--fog',           particles: 'cloud' },
  'fog-night':   { bgClass: 'wx-bg--fog',           particles: 'cloud' },
  'drizzle-day': { bgClass: 'wx-bg--rain-day',      particles: 'rain' },
  'drizzle-night': { bgClass: 'wx-bg--rain-night',  particles: 'rain' },
  'rain-day':    { bgClass: 'wx-bg--rain-day',      particles: 'rain' },
  'rain-night':  { bgClass: 'wx-bg--rain-night',    particles: 'rain' },
  'snow-day':    { bgClass: 'wx-bg--snow-day',      particles: 'snow' },
  'snow-night':  { bgClass: 'wx-bg--snow-night',    particles: 'snow' },
  'thunderstorm-day':  { bgClass: 'wx-bg--thunder',  particles: 'rain' },
  'thunderstorm-night': { bgClass: 'wx-bg--thunder', particles: 'rain' },
};

export function getWeatherBg(code: number, isDay = true): WeatherBgInfo {
  const info = WMO_MAP[code] ?? DEFAULT_INFO;
  const suffix = isDay ? 'day' : 'night';
  const key = `${info.animation}-${suffix}`;
  return BG_MAP[key] ?? { bgClass: 'wx-bg--cloudy-day', particles: 'cloud' };
}
