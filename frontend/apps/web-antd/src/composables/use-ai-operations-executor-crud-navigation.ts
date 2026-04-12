import type { PageOperation } from '#/components/business/ai-runtime/page-operation-types';

import { $t } from '#/locales';
import { router } from '#/router';

import type { CrudOperationExecutorContext } from './use-ai-operations-executor-types';

export function buildCrudNavigationOperations(
  context: CrudOperationExecutorContext,
): PageOperation[] {
  const { detailRoute, hasRecycleBin, openRecycleBin } = context;

  const operations: PageOperation[] = [];

  // ── 7. navigate_to_detail — Navigate to detail (needs detailRoute) / 跳转详情页 ──
  if (detailRoute) {
    operations.push({
      name: 'navigate_to_detail',
      label: $t('shared.pageOperation.navigateToDetail'),
      description: $t('shared.pageOperation.desc.navigateToDetail'),
      readonly: true,
      params: {
        id: {
          type: 'number',
          description: $t('shared.pageOperation.param.recordId'),
          required: true,
        },
      },
      handler: async (params) => {
        const id = params.id;
        if (id === null || id === undefined) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.navigateIdRequired'),
          };
        }
        const path = detailRoute.replace(':id', String(id));
        await router.push(path);
        return {
          success: true,
          message: $t('shared.pageOperation.msg.navigatedTo', { path }),
        };
      },
    });
  }

  // ── 8. view_recycle_bin — Open recycle bin (needs hasRecycleBin) / 打开回收站 ──
  if (hasRecycleBin && openRecycleBin) {
    operations.push({
      name: 'view_recycle_bin',
      label: $t('shared.pageOperation.viewRecycleBin'),
      description: $t('shared.pageOperation.desc.viewRecycleBin'),
      readonly: true,
      handler: async () => {
        openRecycleBin();
        return {
          success: true,
          message: $t('shared.pageOperation.msg.recycleBinOpened'),
        };
      },
    });
  }

  return operations;
}
