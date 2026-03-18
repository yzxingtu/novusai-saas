/**
 * 代码生成器用占位 API / Placeholder APIs for codegen
 *
 * UserSelect、DeptSelect 等组件使用的 API。
 * 待项目实现 /users/select、/departments/tree 等接口后可替换。
 *
 * APIs for UserSelect, DeptSelect etc. Replace when /users/select, /departments/tree are implemented.
 */

/**
 * 用户下拉 API（占位）/ User select API (placeholder)
 *
 * TODO: 对接 GET /admin/users/select 或 GET /tenant/users/select
 */
export async function getUserSelectApi() {
  if (import.meta.env.DEV) {
    console.warn('[getUserSelectApi] Placeholder: /users/select not implemented, returning empty');
  }
  return { items: [] };
}

/**
 * 部门树 API（占位）/ Dept tree API (placeholder)
 *
 * TODO: 对接 GET /admin/departments/tree 或 GET /tenant/departments/tree
 */
export async function getDeptTreeApi() {
  if (import.meta.env.DEV) {
    console.warn('[getDeptTreeApi] Placeholder: /departments/tree not implemented, returning empty');
  }
  return { items: [] };
}
