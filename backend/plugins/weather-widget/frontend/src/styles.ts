/**
 * Weather widget design tokens and shared styles.
 *
 * Styles are injected through JS because popover content is rendered in a portal.
 */
import { WX_BASE } from './styles.base';
import { WX_DASHBOARD } from './styles.dashboard';
import { WX_PANEL } from './styles.panel';
import { WX_RESPONSIVE } from './styles.responsive';
import { WX_SCENE } from './styles.scene';
import { WX_SKELETON } from './styles.skeleton';
import { WX_TRIGGER } from './styles.trigger';

export const WX_STYLES = [
  WX_BASE,
  WX_TRIGGER,
  WX_PANEL,
  WX_SKELETON,
  WX_DASHBOARD,
  WX_SCENE,
  WX_RESPONSIVE,
].join('\n');
