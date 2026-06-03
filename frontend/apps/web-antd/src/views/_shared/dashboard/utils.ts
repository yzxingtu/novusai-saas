import type { SocketIOStatus } from '#/composables/use-socketio';

import { $t } from '#/locales';

export function formatCompactNumber(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }
  return String(value);
}

export function formatCurrency(value: number): string {
  return `$${value.toFixed(2)}`;
}

export function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours <= 0) {
    return `${minutes}m`;
  }
  return `${hours}h ${minutes}m`;
}

export function getSocketStatusLabel(status: SocketIOStatus): string {
  switch (status) {
    case 'connected': {
      return $t('common.socketio.connected');
    }
    case 'reconnecting': {
      return $t('common.socketio.reconnecting');
    }
    default: {
      return $t('common.socketio.disconnected');
    }
  }
}

export function getSocketStatusTone(status: SocketIOStatus): {
  badge: string;
  border: string;
} {
  switch (status) {
    case 'connected': {
      return {
        badge: 'bg-emerald-500/12 text-emerald-700 dark:text-emerald-300',
        border: 'border-emerald-500/20',
      };
    }
    case 'reconnecting': {
      return {
        badge: 'bg-amber-500/12 text-amber-700 dark:text-amber-300',
        border: 'border-amber-500/20',
      };
    }
    default: {
      return {
        badge: 'bg-destructive/12 text-destructive',
        border: 'border-destructive/20',
      };
    }
  }
}
