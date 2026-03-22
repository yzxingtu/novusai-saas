import type { CaptchaConfig } from '#/api/public/config';

import { loadPluginComponents } from '#/utils/plugin-loader';

export async function ensureCaptchaPluginReady(
  captcha: CaptchaConfig | null | undefined,
): Promise<boolean> {
  if (!captcha?.provider || captcha.provider === 'image') {
    return true;
  }

  const plugin = captcha.plugin;
  if (!plugin?.pluginName) {
    return false;
  }

  try {
    await loadPluginComponents(
      plugin.pluginName,
      plugin.frontendRuntime,
      {
        publicEndpoint: plugin.publicEndpoint,
      },
    );
    return true;
  } catch (error) {
    console.warn(
      `[CaptchaPlugin] failed to load provider '${captcha.provider}' from plugin '${plugin.pluginName}'`,
      error,
    );
    return false;
  }
}

export function fallbackToBuiltinCaptcha(
  captcha: CaptchaConfig | null | undefined,
): CaptchaConfig | null | undefined {
  if (!captcha) {
    return captcha;
  }
  return {
    ...captcha,
    plugin: undefined,
    provider: 'image',
    type: 'image',
  };
}
