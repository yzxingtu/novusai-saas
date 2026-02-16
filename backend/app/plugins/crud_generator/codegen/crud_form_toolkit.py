"""
title: CRUD Form Toolkit
description: AI-driven CRUD form configuration tools — fill config, add fields, relations, enums, suggest fields, recommend layout
version: 2.0.0
author: NovusAI
"""

import json


class Tools:
    """CRUD Form Toolkit — 6 tools for AI-driven CRUD configuration filling."""

    def fill_crud_config(self, config: str) -> str:
        """Fill or replace the entire CRUD configuration JSON.

        The config parameter should be a valid JSON string conforming to the
        CrudConfig schema. It must include at minimum: module, table_name,
        display_name, display_name_en, scope, parent_menu, and fields.

        :param config: Complete CrudConfig JSON string
        """
        try:
            parsed = json.loads(config)
        except json.JSONDecodeError as e:
            return json.dumps({
                "__crud_form_fill__": True,
                "error": f"Invalid JSON: {e}",
            })

        return json.dumps({
            "__crud_form_fill__": True,
            "action": "replace",
            "patch": parsed,
        })

    def add_fields(self, fields: str) -> str:
        """Add one or more field definitions to the current CRUD configuration.

        The fields parameter should be a JSON array of FieldConfig objects.
        Each object must include: name (snake_case), type, label_zh, label_en.
        Optional properties: required, nullable, unique, max_length, default,
        enum_ref, searchable, search_op, in_list, in_form, form_component, etc.

        :param fields: JSON array of FieldConfig objects
        """
        try:
            parsed = json.loads(fields)
            if not isinstance(parsed, list):
                parsed = [parsed]
        except json.JSONDecodeError as e:
            return json.dumps({
                "__crud_form_fill__": True,
                "error": f"Invalid JSON: {e}",
            })

        return json.dumps({
            "__crud_form_fill__": True,
            "action": "merge",
            "patch": {"fields": parsed},
        })

    def add_relations(self, relations: str) -> str:
        """Add one or more relation definitions to the current CRUD configuration.

        The relations parameter should be a JSON array of RelationConfig objects.
        Each object must include: name (snake_case), type (belongs_to/has_many/
        many_to_many), target_table, foreign_key.

        :param relations: JSON array of RelationConfig objects
        """
        try:
            parsed = json.loads(relations)
            if not isinstance(parsed, list):
                parsed = [parsed]
        except json.JSONDecodeError as e:
            return json.dumps({
                "__crud_form_fill__": True,
                "error": f"Invalid JSON: {e}",
            })

        return json.dumps({
            "__crud_form_fill__": True,
            "action": "merge",
            "patch": {"relations": parsed},
        })

    def add_enums(self, enums: str) -> str:
        """Add one or more enum definitions to the current CRUD configuration.

        The enums parameter should be a JSON array of EnumDefinition objects.
        Each object must include: name (PascalCase), values (array of
        {value, label_zh, label_en} objects). Optional: description, color, icon,
        transitions (for state machine enums).

        :param enums: JSON array of EnumDefinition objects
        """
        try:
            parsed = json.loads(enums)
            if not isinstance(parsed, list):
                parsed = [parsed]
        except json.JSONDecodeError as e:
            return json.dumps({
                "__crud_form_fill__": True,
                "error": f"Invalid JSON: {e}",
            })

        return json.dumps({
            "__crud_form_fill__": True,
            "action": "merge",
            "patch": {"enums": parsed},
        })

    def suggest_fields(self, module_name: str, existing_fields: str = "[]") -> str:
        """Suggest additional fields for a CRUD module based on the module name
        and any existing fields already defined.

        Analyze the module purpose and recommend fields that are commonly needed
        but not yet included. Return suggested fields as a merge patch.

        :param module_name: The module/business domain name (e.g. 'order', 'article')
        :param existing_fields: JSON array of existing field names to avoid duplicates
        """
        try:
            existing = json.loads(existing_fields) if existing_fields else []
        except json.JSONDecodeError:
            existing = []

        return json.dumps({
            "__crud_form_fill__": True,
            "action": "merge",
            "patch": {"fields": []},
            "meta": {
                "type": "suggestion",
                "module": module_name,
                "existing_count": len(existing),
            },
        })

    def recommend_layout(self, module_name: str, field_count: int = 0) -> str:
        """Recommend list and form layout configuration for a CRUD module.

        Based on the module purpose and field count, suggest optimal list_config
        (columns, sort, filters) and form_config (form type, layout) settings.
        Return as a merge patch for list_config and form_config.

        :param module_name: The module/business domain name
        :param field_count: Number of fields currently defined
        """
        return json.dumps({
            "__crud_form_fill__": True,
            "action": "merge",
            "patch": {},
            "meta": {
                "type": "layout_recommendation",
                "module": module_name,
                "field_count": field_count,
            },
        })

    def generate_migration(self, config: str) -> str:
        """Generate an Alembic migration script from the current CRUD configuration.

        Takes the complete CrudConfig JSON and produces a ready-to-execute
        Alembic migration script with op.create_table(), op.create_index(),
        and a matching downgrade(). The migration file will be placed in
        backend/migrations/versions/crud/.

        :param config: Complete CrudConfig JSON string
        """
        try:
            parsed = json.loads(config)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

        try:
            from app.plugins.crud_generator.codegen.schemas import CrudConfig
            from app.plugins.crud_generator.codegen.generator import CrudGenerator

            crud_config = CrudConfig(**parsed)
            gen = CrudGenerator()
            rel_path, content = gen.generate_migration(crud_config)

            return json.dumps({
                "success": True,
                "migration_path": rel_path,
                "migration_content": content,
                "message": f"Migration script generated: {rel_path}",
            })
        except Exception as e:
            return json.dumps({"error": f"Migration generation failed: {e}"})

    def generate_incremental_migration(self, old_config: str, new_config: str) -> str:
        """Generate an incremental Alembic migration by comparing old and new CrudConfig.

        Detects added, removed, and altered fields/indexes between two versions
        of a CrudConfig, then produces an Alembic migration with add_column,
        drop_column, and alter_column operations.

        :param old_config: Previous CrudConfig JSON string (before changes)
        :param new_config: Updated CrudConfig JSON string (after changes)
        """
        try:
            old_parsed = json.loads(old_config)
            new_parsed = json.loads(new_config)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

        try:
            from app.plugins.crud_generator.codegen.schemas import CrudConfig
            from app.plugins.crud_generator.codegen.generator import CrudGenerator

            old_crud = CrudConfig(**old_parsed)
            new_crud = CrudConfig(**new_parsed)
            gen = CrudGenerator()
            rel_path, content = gen.generate_incremental_migration(old_crud, new_crud)

            if not rel_path:
                return json.dumps({
                    "success": True,
                    "message": "No schema changes detected between old and new config.",
                    "migration_path": "",
                    "migration_content": "",
                })

            return json.dumps({
                "success": True,
                "migration_path": rel_path,
                "migration_content": content,
                "message": f"Incremental migration generated: {rel_path}",
            })
        except Exception as e:
            return json.dumps({"error": f"Incremental migration failed: {e}"})
