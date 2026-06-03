import { TinyColor } from './tinycolor';

export function isDarkColor(color: string) {
  return new TinyColor(color).isDark();
}

export function isLightColor(color: string) {
  return new TinyColor(color).isLight();
}
