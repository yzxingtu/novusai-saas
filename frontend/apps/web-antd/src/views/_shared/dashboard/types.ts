import type { IdentityDisplayModel } from '#/components/business/identity-display';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

export interface DashboardActivityIdentitySource {
  avatar?: null | string;
  display_name?: null | string;
  display_role_name?: null | string;
  is_active?: boolean;
  is_leader?: boolean;
  is_owner?: boolean;
  nickname?: null | string;
  org_node_id?: null | number;
  org_node_name?: null | string;
  role_name?: null | string;
  user_id?: null | number;
  user_type?: null | string;
  username?: null | string;
}

export interface DashboardActivityActor {
  interactive: boolean;
  meta?: IdentityDetailMeta;
  model: IdentityDisplayModel;
}

export interface DashboardActivityEntry {
  actor: DashboardActivityActor;
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
