import type {
  PluginInfo,
  PluginRecoveryAction,
  PluginRecoveryReason,
  PluginRecoveryState,
} from '#/api/admin/plugin';

const DEFAULT_RECOVERY_STATE: PluginRecoveryState = {
  has_scheduled_tasks: false,
  needs_attention: false,
  primary_action: null,
  reason: 'none',
  secondary_actions: [],
  severity: 'healthy',
};

const RECOVERY_REASON_META: Record<
  Exclude<PluginRecoveryReason, 'none'>,
  {
    alertType: 'error' | 'warning';
    descriptionKey: string;
    tagColor: string;
    tagKey: string;
  }
> = {
  missing_dependencies: {
    alertType: 'warning',
    descriptionKey: 'admin.plugin.recovery.description.missingDependencies',
    tagColor: 'warning',
    tagKey: 'admin.plugin.recovery.tag.missingDependencies',
  },
  missing_from_disk: {
    alertType: 'error',
    descriptionKey: 'admin.plugin.recovery.description.missingFromDisk',
    tagColor: 'error',
    tagKey: 'admin.plugin.recovery.tag.missingFromDisk',
  },
  runtime_error: {
    alertType: 'error',
    descriptionKey: 'admin.plugin.recovery.description.runtimeError',
    tagColor: 'error',
    tagKey: 'admin.plugin.recovery.tag.runtimeError',
  },
  schedule_refresh_failed: {
    alertType: 'warning',
    descriptionKey: 'admin.plugin.recovery.description.scheduleRefreshFailed',
    tagColor: 'processing',
    tagKey: 'admin.plugin.recovery.tag.scheduleRefreshFailed',
  },
};

export function getPluginRecoveryState(
  plugin: Pick<PluginInfo, 'manifest' | 'recovery_state'>,
): PluginRecoveryState {
  if (plugin.recovery_state) {
    return plugin.recovery_state;
  }

  const extensions = (plugin.manifest?.extensions || {}) as Record<
    string,
    unknown
  >;
  const tasks = extensions.tasks;

  return {
    ...DEFAULT_RECOVERY_STATE,
    has_scheduled_tasks: Array.isArray(tasks) && tasks.length > 0,
  };
}

export function getPluginRecoveryMeta(
  plugin: Pick<PluginInfo, 'manifest' | 'recovery_state'>,
) {
  const state = getPluginRecoveryState(plugin);
  if (state.reason === 'none') return null;
  return RECOVERY_REASON_META[state.reason];
}

export function hasPluginRecoveryAction(
  plugin: Pick<PluginInfo, 'manifest' | 'recovery_state'>,
  action: PluginRecoveryAction,
): boolean {
  const state = getPluginRecoveryState(plugin);
  return (
    state.primary_action === action || state.secondary_actions.includes(action)
  );
}

export function hasPluginScheduledTasks(
  plugin: Pick<PluginInfo, 'manifest' | 'recovery_state'>,
): boolean {
  return getPluginRecoveryState(plugin).has_scheduled_tasks;
}
