"""Output assembly for codegen generation."""

from __future__ import annotations

import json as _json
from typing import Any

from jinja2 import Environment

from app.codegen import generator_support as support
from app.codegen.config_parser import ParsedConfig
from app.codegen.generator_context_builder import build_generation_context
from app.codegen.generator_types import GeneratedFile, GenerateResult


def assemble_generation_output(
    env: Environment,
    parsed_config: ParsedConfig,
    step: str | None = None,
    *,
    logger: Any,
) -> GenerateResult:
    """生成代码文件列表 / Generate code file list."""
    ctx = build_generation_context(parsed_config)
    files: list[GeneratedFile] = []
    errors: list[str] = []
    resource = parsed_config.resource
    module = parsed_config.module

    if step in (None, "model"):
        try:
            tpl = env.get_template("backend/model.py.j2")
            content = tpl.render(**ctx)
            files.append(
                GeneratedFile(
                    path=f"backend/app/models/{module}/{resource}.py",
                    content=content,
                    action="create",
                )
            )
            files.append(
                GeneratedFile(
                    path=f"backend/app/models/{module}/__init__.py",
                    content="# Codegen module init\n",
                    action="create_if_missing",
                )
            )
            pascal_name = "".join(
                w.capitalize() for w in resource.replace("-", "_").split("_")
            )
            files.append(
                GeneratedFile(
                    path=f"backend/app/models/{module}/__init__.py",
                    content="",
                    action="register_model",
                    model_meta={
                        "module": module,
                        "resource": resource,
                        "pascal": pascal_name,
                        "target": "module",
                    },
                )
            )
            files.append(
                GeneratedFile(
                    path="backend/app/models/__init__.py",
                    content="",
                    action="register_model",
                    model_meta={
                        "module": module,
                        "resource": resource,
                        "pascal": pascal_name,
                        "target": "root",
                    },
                )
            )
            files.append(
                GeneratedFile(
                    path="backend/migrations/env.py",
                    content="",
                    action="register_model",
                    model_meta={
                        "module": module,
                        "resource": resource,
                        "pascal": pascal_name,
                        "target": "env",
                    },
                )
            )
        except Exception as e:
            err_msg = f"model: {e!s}"
            logger.warning("codegen template render failed: {}", e)
            errors.append(err_msg)
        for st in ctx.get("sub_tables") or []:
            sub_res = st.get("resource", "")
            if not sub_res:
                continue
            sub_plural = support.pluralize(sub_res)
            main_fk = st.get("foreign_key") or f"{resource}_id"
            sub_ctx = {
                **ctx,
                "sub_resource": sub_res,
                "sub_resource_plural": sub_plural,
                "main_resource": resource,
                "main_resource_plural": parsed_config.resource_plural,
                "main_fk": main_fk,
                "sub_fields": st.get("fields") or [],
                "sub_display_name": st.get("display_name")
                or sub_res.replace("_", " ").title(),
                "sub_display_name_en": st.get("display_name_en")
                or sub_res.replace("_", " ").title(),
            }
            try:
                tpl = env.get_template("backend/model_sub.py.j2")
                content = tpl.render(**sub_ctx)
                files.append(
                    GeneratedFile(
                        path=f"backend/app/models/{module}/{sub_res}.py",
                        content=content,
                        action="create",
                    )
                )
                sub_pascal = "".join(
                    w.capitalize() for w in sub_res.replace("-", "_").split("_")
                )
                for tgt in ("module", "root", "env"):
                    path_map = {
                        "module": f"backend/app/models/{module}/__init__.py",
                        "root": "backend/app/models/__init__.py",
                        "env": "backend/migrations/env.py",
                    }
                    files.append(
                        GeneratedFile(
                            path=path_map[tgt],
                            content="",
                            action="register_model",
                            model_meta={
                                "module": module,
                                "resource": sub_res,
                                "pascal": sub_pascal,
                                "target": tgt,
                            },
                        )
                    )
            except Exception as e:
                err_msg = f"sub_model:{sub_res}: {e!s}"
                logger.warning("codegen sub model template render failed: {}", e)
                errors.append(err_msg)
        files.append(
            GeneratedFile(
                path=f"backend/app/schemas/{module}/__init__.py",
                content="# Codegen module init\n",
                action="create_if_missing",
            )
        )
        try:
            tpl = env.get_template("backend/schema.py.j2")
            content = tpl.render(**ctx)
            files.append(
                GeneratedFile(
                    path=f"backend/app/schemas/{module}/{resource}.py",
                    content=content,
                    action="create",
                )
            )
        except Exception as e:
            err_msg = f"schema: {e!s}"
            logger.warning("codegen template render failed: {}", e)
            errors.append(err_msg)
        files.append(
            GeneratedFile(
                path=f"backend/app/repositories/{module}/__init__.py",
                content="# Codegen module init\n",
                action="create_if_missing",
            )
        )
        try:
            tpl = env.get_template("backend/repository.py.j2")
            content = tpl.render(**ctx)
            files.append(
                GeneratedFile(
                    path=f"backend/app/repositories/{module}/{resource}_repository.py",
                    content=content,
                    action="create",
                )
            )
        except Exception as e:
            err_msg = f"repository: {e!s}"
            logger.warning("codegen template render failed: {}", e)
            errors.append(err_msg)
        files.append(
            GeneratedFile(
                path=f"backend/app/services/{module}/__init__.py",
                content="# Codegen module init\n",
                action="create_if_missing",
            )
        )
        try:
            tpl = env.get_template("backend/service.py.j2")
            content = tpl.render(**ctx)
            files.append(
                GeneratedFile(
                    path=f"backend/app/services/{module}/{resource}_service.py",
                    content=content,
                    action="create",
                )
            )
        except Exception as e:
            err_msg = f"service: {e!s}"
            logger.warning("codegen template render failed: {}", e)
            errors.append(err_msg)
        display_name = parsed_config.display_name or resource.replace("_", " ").title()
        display_name_en = (
            parsed_config.display_name_en or resource.replace("_", " ").title()
        )
        res_name = resource.replace("_", "-")
        i18n_zh = {
            module: {
                resource: {
                    "not_found": f"{display_name}不存在",
                    "created": f"{display_name}创建成功",
                    "updated": f"{display_name}更新成功",
                }
            },
            "action": {
                res_name: {
                    "list": f"查看{display_name}",
                    "create": f"创建{display_name}",
                    "update": f"更新{display_name}",
                    "delete": f"删除{display_name}",
                }
            },
        }
        i18n_en = {
            module: {
                resource: {
                    "not_found": f"{display_name_en} not found",
                    "created": f"{display_name_en} created successfully",
                    "updated": f"{display_name_en} updated successfully",
                }
            },
            "action": {
                res_name: {
                    "list": f"View {display_name_en}",
                    "create": f"Create {display_name_en}",
                    "update": f"Update {display_name_en}",
                    "delete": f"Delete {display_name_en}",
                }
            },
        }
        merged_keys = [f"{module}.{resource}", f"action.{res_name}"]
        files.append(
            GeneratedFile(
                path="backend/app/locales/zh_CN/messages.json",
                content=_json.dumps(i18n_zh, ensure_ascii=False),
                action="merge_json",
                merged_keys=merged_keys,
            )
        )
        files.append(
            GeneratedFile(
                path="backend/app/locales/en/messages.json",
                content=_json.dumps(i18n_en, ensure_ascii=False),
                action="merge_json",
                merged_keys=merged_keys,
            )
        )

    if step in (None, "controller"):
        admin_eps = [
            e
            for e in (parsed_config.endpoints or [])
            if (e or {}).get("scope") in ("admin", "admin_only")
        ]
        if admin_eps:
            try:
                tpl = env.get_template("backend/controller_admin.py.j2")
                content = tpl.render(**ctx)
                files.append(
                    GeneratedFile(
                        path=f"backend/app/api/admin/{resource}.py",
                        content=content,
                        action="create",
                    )
                )
                files.append(
                    GeneratedFile(
                        path="backend/app/api/admin/__init__.py",
                        content="",
                        action="register_route",
                        route_meta={"scope": "admin", "resource": resource},
                    )
                )
            except Exception as e:
                err_msg = f"controller_admin: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)
        tenant_eps = [
            e
            for e in (parsed_config.endpoints or [])
            if (e or {}).get("scope") in ("tenant", "tenant_only")
        ]
        if tenant_eps:
            try:
                tpl = env.get_template("backend/controller_tenant.py.j2")
                content = tpl.render(**ctx)
                files.append(
                    GeneratedFile(
                        path=f"backend/app/api/tenant/{resource}.py",
                        content=content,
                        action="create",
                    )
                )
                files.append(
                    GeneratedFile(
                        path="backend/app/api/tenant/__init__.py",
                        content="",
                        action="register_route",
                        route_meta={"scope": "tenant", "resource": resource},
                    )
                )
            except Exception as e:
                err_msg = f"controller_tenant: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)

    if step in (None, "test"):
        try:
            tpl = env.get_template("backend/test_service.py.j2")
            content = tpl.render(**ctx)
            files.append(
                GeneratedFile(
                    path=f"backend/tests/services/{module}/test_{resource}_service.py",
                    content=content,
                    action="create",
                )
            )
        except Exception as e:
            err_msg = f"test_service: {e!s}"
            logger.warning("codegen template render failed: {}", e)
            errors.append(err_msg)

    if step in (None, "frontend"):
        frontend_root = "frontend/apps/web-antd/src"
        admin_ep = ctx.get("admin_ep") or {}
        tenant_ep = ctx.get("tenant_ep") or {}
        mode = (
            (admin_ep.get("frontend") or {}).get("mode")
            or (tenant_ep.get("frontend") or {}).get("mode")
            or "table"
        )

        if admin_ep:
            _menu_path = (admin_ep.get("permission") or {}).get("menu") or {}
            _raw_path = (
                _menu_path.get("path")
                or f"/{module.replace('_', '-')}/{resource.replace('_', '-')}s"
            )
            _list_path = _raw_path.lstrip("/")
            render_ctx = {
                **ctx,
                "api_scope": "admin",
                "i18n_prefix": f"admin.{module}.{resource}",
                "list_path": _list_path,
            }
            try:
                tpl = env.get_template("frontend/api_admin.ts.j2")
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/api/admin/{resource}.ts",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"api_admin: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)
            try:
                tpl = env.get_template(
                    "frontend/data_table.ts.j2"
                    if mode == "table"
                    else "frontend/data_card.ts.j2"
                )
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/views/admin/{module}/{resource}/data.ts",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"data_admin: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)
            try:
                tpl = env.get_template(
                    "frontend/index_table.vue.j2"
                    if mode == "table"
                    else "frontend/index_card.vue.j2"
                )
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/views/admin/{module}/{resource}/index.vue",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"index_admin: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)
            try:
                tpl = env.get_template("frontend/form.vue.j2")
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/views/admin/{module}/{resource}/modules/form.vue",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"form_admin: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)
            if (ctx.get("detail") or {}).get("enabled"):
                detail_cfg = ctx.get("detail") or {}
                detail_mode = detail_cfg.get("mode") or "drawer"
                try:
                    if detail_mode == "page":
                        tpl = env.get_template("frontend/detail_page.vue.j2")
                        content = tpl.render(**render_ctx)
                        files.append(
                            GeneratedFile(
                                path=f"{frontend_root}/views/admin/{module}/{resource}/detail.vue",
                                content=content,
                                action="create",
                            )
                        )
                        route_block = (
                            "    // Codegen auto-registered: {resource} detail\n"
                            "    {{\n"
                            "      name: 'Admin{resource_pascal}Detail',\n"
                            "      path: '{list_path}/:id',\n"
                            "      component: () => import('#/views/admin/{module}/{resource}/detail.vue'),\n"
                            "      meta: {{\n"
                            "        hideInMenu: true,\n"
                            "        title: $t('admin.{module}.{resource}.detail'),\n"
                            "        activePath: '/admin/{list_path}',\n"
                            "      }},\n"
                            "    }},\n"
                        ).format(
                            resource=resource,
                            resource_pascal="".join(
                                w.capitalize()
                                for w in resource.replace("-", "_").split("_")
                            ),
                            list_path=_list_path,
                            module=module,
                        )
                        files.append(
                            GeneratedFile(
                                path=f"{frontend_root}/router/routes/admin/index.ts",
                                content="",
                                action="append",
                                appended_content=route_block.strip(),
                                insert_before_last_marker="  ],",
                            )
                        )
                    else:
                        tpl = env.get_template("frontend/detail.vue.j2")
                        content = tpl.render(**render_ctx)
                        files.append(
                            GeneratedFile(
                                path=f"{frontend_root}/views/admin/{module}/{resource}/modules/detail.vue",
                                content=content,
                                action="create",
                            )
                        )
                except Exception as e:
                    err_msg = f"detail_admin: {e!s}"
                    logger.warning("codegen detail template render failed: {}", e)
                    errors.append(err_msg)
            try:
                tpl = env.get_template("frontend/i18n_zh.json.j2")
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/locales/langs/zh-CN/admin/{module}/{resource}.json",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"i18n_zh_admin: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)
            try:
                tpl = env.get_template("frontend/i18n_en.json.j2")
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/locales/langs/en-US/admin/{module}/{resource}.json",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"i18n_en_admin: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)

        if tenant_ep:
            _menu_path_tenant = (tenant_ep.get("permission") or {}).get("menu") or {}
            _raw_path_tenant = (
                _menu_path_tenant.get("path")
                or f"/{module.replace('_', '-')}/{resource.replace('_', '-')}s"
            )
            _list_path_tenant = _raw_path_tenant.lstrip("/")
            render_ctx = {
                **ctx,
                "api_scope": "tenant",
                "i18n_prefix": f"tenant.{module}.{resource}",
                "list_path": _list_path_tenant,
            }
            try:
                tpl = env.get_template("frontend/api_tenant.ts.j2")
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/api/tenant/{resource}.ts",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"api_tenant: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)
            try:
                tpl = env.get_template(
                    "frontend/data_table.ts.j2"
                    if mode == "table"
                    else "frontend/data_card.ts.j2"
                )
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/views/tenant/{module}/{resource}/data.ts",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"data_tenant: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)
            try:
                tpl = env.get_template(
                    "frontend/index_table.vue.j2"
                    if mode == "table"
                    else "frontend/index_card.vue.j2"
                )
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/views/tenant/{module}/{resource}/index.vue",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"index_tenant: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)
            try:
                tpl = env.get_template("frontend/form.vue.j2")
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/views/tenant/{module}/{resource}/modules/form.vue",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"form_tenant: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)
            if (ctx.get("detail") or {}).get("enabled"):
                detail_cfg = ctx.get("detail") or {}
                detail_mode = detail_cfg.get("mode") or "drawer"
                try:
                    if detail_mode == "page":
                        tpl = env.get_template("frontend/detail_page.vue.j2")
                        content = tpl.render(**render_ctx)
                        files.append(
                            GeneratedFile(
                                path=f"{frontend_root}/views/tenant/{module}/{resource}/detail.vue",
                                content=content,
                                action="create",
                            )
                        )
                        route_block = (
                            "    // Codegen auto-registered: {resource} detail\n"
                            "    {{\n"
                            "      name: 'Tenant{resource_pascal}Detail',\n"
                            "      path: '{list_path}/:id',\n"
                            "      component: () => import('#/views/tenant/{module}/{resource}/detail.vue'),\n"
                            "      meta: {{\n"
                            "        hideInMenu: true,\n"
                            "        title: $t('tenant.{module}.{resource}.detail'),\n"
                            "        activePath: '/tenant/{list_path}',\n"
                            "      }},\n"
                            "    }},\n"
                        ).format(
                            resource=resource,
                            resource_pascal="".join(
                                w.capitalize()
                                for w in resource.replace("-", "_").split("_")
                            ),
                            list_path=_list_path_tenant,
                            module=module,
                        )
                        files.append(
                            GeneratedFile(
                                path=f"{frontend_root}/router/routes/tenant/index.ts",
                                content="",
                                action="append",
                                appended_content=route_block.strip(),
                                insert_before_last_marker="  ],",
                            )
                        )
                    else:
                        tpl = env.get_template("frontend/detail.vue.j2")
                        content = tpl.render(**render_ctx)
                        files.append(
                            GeneratedFile(
                                path=f"{frontend_root}/views/tenant/{module}/{resource}/modules/detail.vue",
                                content=content,
                                action="create",
                            )
                        )
                except Exception as e:
                    err_msg = f"detail_tenant: {e!s}"
                    logger.warning("codegen detail template render failed: {}", e)
                    errors.append(err_msg)
            try:
                tpl = env.get_template("frontend/i18n_zh.json.j2")
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/locales/langs/zh-CN/tenant/{module}/{resource}.json",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"i18n_zh_tenant: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)
            try:
                tpl = env.get_template("frontend/i18n_en.json.j2")
                content = tpl.render(**render_ctx)
                files.append(
                    GeneratedFile(
                        path=f"{frontend_root}/locales/langs/en-US/tenant/{module}/{resource}.json",
                        content=content,
                        action="create",
                    )
                )
            except Exception as e:
                err_msg = f"i18n_en_tenant: {e!s}"
                logger.warning("codegen template render failed: {}", e)
                errors.append(err_msg)

    if step in (None, "controller"):
        display_name = parsed_config.display_name or resource.replace("_", " ").title()
        display_name_en = (
            parsed_config.display_name_en or resource.replace("_", " ").title()
        )
        admin_ep = ctx.get("admin_ep") or {}
        tenant_ep = ctx.get("tenant_ep") or {}
        menu_zh: dict[str, dict[str, str]] = {}
        menu_en: dict[str, dict[str, str]] = {}
        if admin_ep:
            menu_zh.setdefault("admin", {})[resource] = display_name
            menu_en.setdefault("admin", {})[resource] = display_name_en
        if tenant_ep:
            menu_zh.setdefault("tenant", {})[resource] = display_name
            menu_en.setdefault("tenant", {})[resource] = display_name_en
        if menu_zh:
            merged_keys_list = []
            if admin_ep:
                merged_keys_list.append(f"menu.admin.{resource}")
            if tenant_ep:
                merged_keys_list.append(f"menu.tenant.{resource}")
            files.append(
                GeneratedFile(
                    path="backend/app/locales/zh_CN/menu.json",
                    content=_json.dumps({"menu": menu_zh}, ensure_ascii=False),
                    action="merge_json",
                    merged_keys=merged_keys_list,
                )
            )
            files.append(
                GeneratedFile(
                    path="backend/app/locales/en/menu.json",
                    content=_json.dumps({"menu": menu_en}, ensure_ascii=False),
                    action="merge_json",
                    merged_keys=merged_keys_list,
                )
            )

    return GenerateResult(files=files, errors=errors)


__all__ = ["assemble_generation_output"]
