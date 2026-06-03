import { describe, expect, it } from 'vitest';

import {
  getPluginRecoveryMeta,
  getPluginRecoveryState,
  hasPluginRecoveryAction,
  hasPluginScheduledTasks,
} from '../plugin-recovery';

describe('plugin-recovery', () => {
  it('uses backend recovery state when present', () => {
    const plugin: Parameters<typeof getPluginRecoveryState>[0] = {
      manifest: {},
      recovery_state: {
        has_scheduled_tasks: true,
        needs_attention: true,
        primary_action: 'refresh_schedules',
        reason: 'schedule_refresh_failed',
        secondary_actions: [],
        severity: 'error',
      },
    };

    expect(getPluginRecoveryState(plugin).reason).toBe(
      'schedule_refresh_failed',
    );
    expect(hasPluginScheduledTasks(plugin)).toBe(true);
    expect(hasPluginRecoveryAction(plugin, 'refresh_schedules')).toBe(true);
    expect(getPluginRecoveryMeta(plugin)?.tagKey).toBe(
      'admin.plugin.recovery.tag.scheduleRefreshFailed',
    );
  });

  it('falls back to manifest task detection when recovery state is absent', () => {
    const plugin: Parameters<typeof getPluginRecoveryState>[0] = {
      manifest: {
        extensions: {
          tasks: [{ name: 'digest' }],
        },
      },
    };

    const state = getPluginRecoveryState(plugin);

    expect(state.needs_attention).toBe(false);
    expect(state.has_scheduled_tasks).toBe(true);
    expect(getPluginRecoveryMeta(plugin)).toBeNull();
  });

  it('recognizes secondary recovery actions', () => {
    const plugin: Parameters<typeof getPluginRecoveryState>[0] = {
      manifest: {},
      recovery_state: {
        has_scheduled_tasks: false,
        needs_attention: true,
        primary_action: 'install_dependencies',
        reason: 'missing_dependencies',
        secondary_actions: ['repair'],
        severity: 'error',
      },
    };

    expect(hasPluginRecoveryAction(plugin, 'install_dependencies')).toBe(true);
    expect(hasPluginRecoveryAction(plugin, 'repair')).toBe(true);
    expect(hasPluginRecoveryAction(plugin, 'force_cleanup')).toBe(false);
  });
});
