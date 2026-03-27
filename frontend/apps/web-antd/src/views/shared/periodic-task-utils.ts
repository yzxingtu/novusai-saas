/**
 * 定时任务调度类型显示 - 共享工具
 * Shared utility for periodic task schedule type display
 */
import { $t } from '#/locales';

export type PeriodicTaskScope = 'admin' | 'tenant';

/**
 * 获取调度类型文本（支持 admin/tenant 两种命名空间）
 */
export function getScheduleTypeText(
  type: string | undefined,
  scope: PeriodicTaskScope = 'admin',
): string {
  if (!type) return '-';
  const base =
    scope === 'admin'
      ? 'admin.system.periodicTask'
      : 'tenant.system.periodicTask';
  switch (type) {
    case 'cron': {
      return $t(`${base}.scheduleType.cron`);
    }
    case 'interval': {
      return $t(`${base}.scheduleType.interval`);
    }
    default: {
      return type;
    }
  }
}
