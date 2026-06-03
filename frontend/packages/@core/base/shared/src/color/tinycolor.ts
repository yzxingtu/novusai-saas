interface HslColor {
  a: number;
  h: number;
  l: number;
  s: number;
}

interface RgbaColor {
  a: number;
  b: number;
  g: number;
  r: number;
}

const NAMED_COLORS: Record<string, string> = {
  black: '#000000',
  blue: '#0000ff',
  cyan: '#00ffff',
  gray: '#808080',
  green: '#008000',
  grey: '#808080',
  orange: '#ffa500',
  pink: '#ffc0cb',
  purple: '#800080',
  red: '#ff0000',
  transparent: '#00000000',
  white: '#ffffff',
  yellow: '#ffff00',
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function roundChannel(value: number) {
  return Math.round(clamp(value, 0, 255));
}

function normalizeHue(input: string) {
  const value = Number.parseFloat(input);
  if (!Number.isFinite(value)) {
    return null;
  }

  if (input.endsWith('grad')) {
    return (value * 360) / 400;
  }
  if (input.endsWith('rad')) {
    return (value * 180) / Math.PI;
  }
  if (input.endsWith('turn')) {
    return value * 360;
  }
  return value;
}

function parseAlpha(input: string) {
  const trimmed = input.trim();
  if (trimmed.endsWith('%')) {
    const value = Number.parseFloat(trimmed);
    return Number.isFinite(value) ? clamp(value / 100, 0, 1) : null;
  }
  const value = Number.parseFloat(trimmed);
  return Number.isFinite(value) ? clamp(value, 0, 1) : null;
}

function parseRgbChannel(input: string) {
  const trimmed = input.trim();
  if (trimmed.endsWith('%')) {
    const value = Number.parseFloat(trimmed);
    return Number.isFinite(value) ? roundChannel((value / 100) * 255) : null;
  }
  const value = Number.parseFloat(trimmed);
  return Number.isFinite(value) ? roundChannel(value) : null;
}

function parsePercentage(input: string) {
  const trimmed = input.trim();
  const value = Number.parseFloat(trimmed);
  if (!Number.isFinite(value)) {
    return null;
  }
  if (trimmed.endsWith('%')) {
    return clamp(value / 100, 0, 1);
  }
  return clamp(value, 0, 1);
}

function hslToRgb(h: number, s: number, l: number) {
  const hue = ((h % 360) + 360) % 360;
  const chroma = (1 - Math.abs(2 * l - 1)) * s;
  const segment = hue / 60;
  const x = chroma * (1 - Math.abs((segment % 2) - 1));

  let red = 0;
  let green = 0;
  let blue = 0;

  if (segment >= 0 && segment < 1) {
    red = chroma;
    green = x;
  } else if (segment < 2) {
    red = x;
    green = chroma;
  } else if (segment < 3) {
    green = chroma;
    blue = x;
  } else if (segment < 4) {
    green = x;
    blue = chroma;
  } else if (segment < 5) {
    red = x;
    blue = chroma;
  } else {
    red = chroma;
    blue = x;
  }

  const match = l - chroma / 2;
  return {
    r: roundChannel((red + match) * 255),
    g: roundChannel((green + match) * 255),
    b: roundChannel((blue + match) * 255),
  };
}

function rgbToHsl(r: number, g: number, b: number): Omit<HslColor, 'a'> {
  const red = clamp(r / 255, 0, 1);
  const green = clamp(g / 255, 0, 1);
  const blue = clamp(b / 255, 0, 1);

  const max = Math.max(red, green, blue);
  const min = Math.min(red, green, blue);
  const delta = max - min;

  let hue = 0;
  if (delta !== 0) {
    if (max === red) {
      hue = ((green - blue) / delta) % 6;
    } else if (max === green) {
      hue = (blue - red) / delta + 2;
    } else {
      hue = (red - green) / delta + 4;
    }
  }

  hue = Math.round((hue * 60 + 360) % 360);
  const lightness = (max + min) / 2;
  const saturation =
    delta === 0 ? 0 : delta / (1 - Math.abs(2 * lightness - 1));

  return {
    h: hue,
    s: saturation,
    l: lightness,
  };
}

function parseHexColor(input: string): null | RgbaColor {
  const normalized = input.trim().replace(/^#/, '');
  if (!/^[\da-f]+$/i.test(normalized)) {
    return null;
  }

  const expand = (token: string) => token + token;
  if (normalized.length === 3 || normalized.length === 4) {
    const chars = [...normalized];
    const [r = '', g = '', b = '', a = 'f'] = chars.map((token) =>
      expand(token),
    );
    return {
      r: Number.parseInt(r, 16),
      g: Number.parseInt(g, 16),
      b: Number.parseInt(b, 16),
      a: Number.parseInt(a, 16) / 255,
    };
  }

  if (normalized.length === 6 || normalized.length === 8) {
    const alpha = normalized.length === 8 ? normalized.slice(6, 8) : 'ff';
    return {
      r: Number.parseInt(normalized.slice(0, 2), 16),
      g: Number.parseInt(normalized.slice(2, 4), 16),
      b: Number.parseInt(normalized.slice(4, 6), 16),
      a: Number.parseInt(alpha, 16) / 255,
    };
  }

  return null;
}

function parseRgbColor(input: string): null | RgbaColor {
  const match = input.trim().match(/^rgba?\((.*)\)$/i);
  if (!match) {
    return null;
  }

  const body = match[1]?.trim() || '';
  let rgbParts: string[] = [];
  let alphaPart: string | undefined;

  if (body.includes(',')) {
    const parts = body.split(',').map((part) => part.trim());
    rgbParts = parts.slice(0, 3);
    alphaPart = parts[3];
  } else {
    const [channels = '', alpha] = body.split('/').map((part) => part.trim());
    rgbParts = channels.split(/\s+/).filter(Boolean);
    alphaPart = alpha;
  }

  if (rgbParts.length !== 3) {
    return null;
  }

  const r = parseRgbChannel(rgbParts[0] || '');
  const g = parseRgbChannel(rgbParts[1] || '');
  const b = parseRgbChannel(rgbParts[2] || '');
  const a = alphaPart ? parseAlpha(alphaPart) : 1;

  if (r === null || g === null || b === null || a === null) {
    return null;
  }

  return { r, g, b, a };
}

function parseHslColor(input: string): null | RgbaColor {
  const match = input.trim().match(/^hsla?\((.*)\)$/i);
  if (!match) {
    return null;
  }

  const body = match[1]?.trim() || '';
  let hslParts: string[] = [];
  let alphaPart: string | undefined;

  if (body.includes(',')) {
    const parts = body.split(',').map((part) => part.trim());
    hslParts = parts.slice(0, 3);
    alphaPart = parts[3];
  } else {
    const [channels = '', alpha] = body.split('/').map((part) => part.trim());
    hslParts = channels.split(/\s+/).filter(Boolean);
    alphaPart = alpha;
  }

  if (hslParts.length !== 3) {
    return null;
  }

  const h = normalizeHue(hslParts[0] || '');
  const s = parsePercentage(hslParts[1] || '');
  const l = parsePercentage(hslParts[2] || '');
  const a = alphaPart ? parseAlpha(alphaPart) : 1;

  if (h === null || s === null || l === null || a === null) {
    return null;
  }

  return { ...hslToRgb(h, s, l), a };
}

function normalizeDomColor(input: string) {
  if (typeof document === 'undefined') {
    return null;
  }

  const element = document.createElement('span');
  element.style.color = '';
  element.style.color = input;
  if (!element.style.color) {
    return null;
  }

  if (document.body) {
    document.body.append(element);
    const computedColor = globalThis.getComputedStyle?.(element).color || null;
    element.remove();
    return computedColor || element.style.color || null;
  }

  return element.style.color || null;
}

function parseColor(input?: string): null | RgbaColor {
  if (!input) {
    return null;
  }

  const trimmed = input.trim();
  if (!trimmed) {
    return null;
  }

  const normalized = trimmed.toLowerCase();
  const direct =
    parseHexColor(normalized) ||
    parseRgbColor(normalized) ||
    parseHslColor(normalized);
  if (direct) {
    return direct;
  }

  const named = NAMED_COLORS[normalized];
  if (named) {
    return parseHexColor(named);
  }

  const domColor = normalizeDomColor(trimmed);
  if (domColor && domColor.toLowerCase() !== normalized) {
    return (
      parseHexColor(domColor) ||
      parseRgbColor(domColor) ||
      parseHslColor(domColor)
    );
  }

  return null;
}

function toHexChannel(value: number) {
  return roundChannel(value).toString(16).padStart(2, '0');
}

export class TinyColor {
  get isValid() {
    return this.#rgba !== null;
  }

  #rgba: null | RgbaColor;

  constructor(color?: string) {
    this.#rgba = parseColor(color);
  }

  isDark() {
    if (!this.#rgba) {
      return false;
    }
    const { r, g, b } = this.#rgba;
    const brightness = (r * 299 + g * 587 + b * 114) / 1000;
    return brightness < 128;
  }

  isLight() {
    return this.isValid && !this.isDark();
  }

  toHexString() {
    if (!this.#rgba) {
      return '#000000';
    }
    const { r, g, b } = this.#rgba;
    return `#${toHexChannel(r)}${toHexChannel(g)}${toHexChannel(b)}`;
  }

  toHsl(): HslColor {
    if (!this.#rgba) {
      return { a: 1, h: 0, l: 0, s: 0 };
    }
    const { a, b, g, r } = this.#rgba;
    return {
      ...rgbToHsl(r, g, b),
      a,
    };
  }

  toRgbString() {
    if (!this.#rgba) {
      return 'rgb(0, 0, 0)';
    }
    const { a, b, g, r } = this.#rgba;
    return a < 1 ? `rgba(${r}, ${g}, ${b}, ${a})` : `rgb(${r}, ${g}, ${b})`;
  }
}
