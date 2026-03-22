export interface DashboardActivityEntry {
  actor: string;
  createdAt: null | string;
  detail: string;
  id: number | string;
  method: string;
  path: string;
  statusCode?: null | number;
}

export interface DashboardChip {
  badge: string;
  border: string;
  icon: string;
  key: string;
  text: string;
}

export interface DashboardHeroAction {
  icon?: string;
  key: string;
  label: string;
  route: string;
  variant?: 'primary' | 'secondary';
}

export interface DashboardMetricCard {
  icon: string;
  key: string;
  label: string;
  value: string;
}

export interface DashboardRouteCardItem {
  description: string;
  icon: string;
  key: string;
  route: string;
  title: string;
  value?: string;
}

export interface DashboardSpotlightItem {
  detail?: string;
  icon: string;
  key: string;
  label: string;
  tone?: 'default' | 'positive' | 'warning';
  value: string;
}

export interface DashboardSummaryPanel {
  icon: string;
  key: string;
  rows: Array<{
    label: string;
    value: string;
  }>;
  title: string;
}
