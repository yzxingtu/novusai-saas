/**
 * DOM Semantic Scanner
 * DOM 语义快照扫描器
 *
 * Provides a fallback page context for pages that have not called registerPageContext().
 * Scans the DOM for key semantic elements (headings, tables, forms, buttons, tabs)
 * and returns a lightweight snapshot the AI can use to understand the page.
 *
 * Security: never extracts input values (only labels/headings).
 * Performance: capped at 50ms scan budget; output capped at ~2KB JSON.
 */

export interface DomSnapshot {
  page_title: string;
  breadcrumb: string[];
  tables: Array<{ columns: string[]; row_count: number }>;
  forms: Array<{ labels: string[] }>;
  action_buttons: string[];
  tabs: Array<{ label: string; active: boolean }>;
}

const MAX_OUTPUT_BYTES = 2048;
const MAX_BUTTONS = 15;
const MAX_LABELS_PER_FORM = 20;
const MAX_COLUMNS = 15;

function textOf(el: Element | null): string {
  return el?.textContent?.trim().slice(0, 80) || '';
}

/**
 * Scan the current page DOM and return a semantic snapshot / 扫描当前页 DOM 并返回语义快照
 * Returns null if no meaningful content is found.
 */
export function scanDomSemantics(): DomSnapshot | null {
  const start = performance.now();

  // 1. Page title — breadcrumb last item or header title / 页面标题
  let pageTitle = '';
  const breadcrumbItems = document.querySelectorAll(
    '.ant-breadcrumb-link, .vben-breadcrumb .breadcrumb-label',
  );
  const breadcrumb: string[] = [];
  breadcrumbItems.forEach((el) => {
    const t = textOf(el);
    if (t) breadcrumb.push(t);
  });
  if (breadcrumb.length > 0) {
    pageTitle = breadcrumb[breadcrumb.length - 1]!;
  }
  if (!pageTitle) {
    pageTitle =
      textOf(document.querySelector('.vben-page-header-title')) ||
      textOf(document.querySelector('h1')) ||
      textOf(document.querySelector('.ant-page-header-heading-title')) ||
      '';
  }

  // 2. Tables / 表格
  const tables: DomSnapshot['tables'] = [];
  const tableEls = document.querySelectorAll(
    '.ant-table, .vxe-table, [class*="vxe-grid"]',
  );
  tableEls.forEach((tableEl) => {
    if (performance.now() - start > 40) return;

    const columns: string[] = [];
    const headerCells = tableEl.querySelectorAll(
      '.ant-table-thead th, .vxe-header--column .vxe-cell--title',
    );
    headerCells.forEach((th) => {
      if (columns.length >= MAX_COLUMNS) return;
      const t = textOf(th);
      if (t) columns.push(t);
    });

    let rowCount = 0;
    const rows = tableEl.querySelectorAll(
      '.ant-table-tbody tr, .vxe-body--row',
    );
    rowCount = rows.length;

    if (columns.length > 0) {
      tables.push({ columns, row_count: rowCount });
    }
  });

  // 3. Forms (labels only, no values) / 表单仅采集标签不含值
  const forms: DomSnapshot['forms'] = [];
  const formEls = document.querySelectorAll('form, .ant-form');
  formEls.forEach((formEl) => {
    if (performance.now() - start > 40) return;

    const labels: string[] = [];
    formEl.querySelectorAll('.ant-form-item-label label').forEach((lbl) => {
      if (labels.length >= MAX_LABELS_PER_FORM) return;
      const t = textOf(lbl);
      if (t) labels.push(t);
    });
    if (labels.length > 0) {
      forms.push({ labels });
    }
  });

  // 4. Action buttons / 操作按钮
  const actionButtons: string[] = [];
  const buttons = document.querySelectorAll(
    'button:not([disabled]):not(.ant-modal button):not(.ant-drawer button)',
  );
  buttons.forEach((btn) => {
    if (actionButtons.length >= MAX_BUTTONS) return;
    const t = textOf(btn);
    if (t && t.length > 1 && t.length < 30) {
      actionButtons.push(t);
    }
  });

  // 5. Tabs / 页签
  const tabs: DomSnapshot['tabs'] = [];
  document.querySelectorAll('.ant-tabs-tab').forEach((tabEl) => {
    const label = textOf(tabEl);
    if (label) {
      tabs.push({
        label,
        active: tabEl.classList.contains('ant-tabs-tab-active'),
      });
    }
  });

  // Empty check — return null if nothing meaningful found / 无有效内容则返回 null
  if (
    !pageTitle &&
    breadcrumb.length === 0 &&
    tables.length === 0 &&
    forms.length === 0 &&
    actionButtons.length === 0 &&
    tabs.length === 0
  ) {
    return null;
  }

  const snapshot: DomSnapshot = {
    page_title: pageTitle,
    breadcrumb,
    tables,
    forms,
    action_buttons: actionButtons,
    tabs,
  };

  // Size guard: if serialized output exceeds budget, trim sample_rows/buttons / 超长则裁剪
  const serialized = JSON.stringify(snapshot);
  if (serialized.length > MAX_OUTPUT_BYTES) {
    snapshot.action_buttons = snapshot.action_buttons.slice(0, 8);
    snapshot.tables = snapshot.tables.map((t) => ({
      columns: t.columns.slice(0, 8),
      row_count: t.row_count,
    }));
  }

  return snapshot;
}
