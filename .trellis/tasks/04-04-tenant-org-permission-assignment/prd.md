# Tenant Organization Permission Assignment Parity

## Goal
排查并修复企业端组织架构页面缺少权限分配能力的问题，使其与管理端组织节点的权限分配能力保持一致。

## Requirements
- 对比 `/tenant/system/organization` 与 `/admin/system/organization` 的前后端实现。
- 若企业端组织节点权限分配是遗漏实现，则补齐 tenant 端模型、接口、前端展示与编辑能力。
- 保持权限范围限定在 tenant/both 端权限，不错误下放平台端专属权限。
- 同步补充 i18n、权限预览、表单编辑与规范说明。

## Acceptance Criteria
- [ ] 企业端组织节点详情可看到权限数量与权限预览。
- [ ] 企业端组织节点新建/编辑弹窗可分配权限，并能正确保存。
- [ ] tenant 后端组织节点详情/创建/更新契约支持 `permission_ids` 等所需字段。
- [ ] 项目规范补充“企业端组织节点权限分配不能遗漏”的检查项。

## Technical Notes
- 优先复用管理端组织节点权限分配的已有模式。
- 如需新增 tenant 组织节点权限关联表，按 Alembic 规范补迁移文件并注册模型。
