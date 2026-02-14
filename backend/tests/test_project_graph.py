"""
ProjectGraph — 单元测试

覆盖：
- 单实体 graph
- 链式依赖（A → B → C）
- 菱形依赖（A → B, A → C, B → D, C → D）
- 循环依赖时 issues 包含 cycle
- cross_relations 边正确
- generation_order 正确
- shared_enums warnings
"""

import pytest

from app.codegen.project_graph import (
    GRAPH_VERSION,
    ProjectGraph,
    build_project_graph,
)
from app.codegen.schemas import BatchCrudProject


def _entity(module: str, table: str, display: str, display_en: str = "") -> dict:
    """最小实体"""
    return {
        "module": module,
        "table_name": table,
        "display_name": display,
        "display_name_en": display_en or module.title(),
        "parent_menu": "test",
        "fields": [
            {
                "name": "title",
                "type": "string",
                "label": "Title",
                "label_zh": "标题",
                "label_en": "Title",
            },
        ],
    }


def _relation(source: str, target: str, rel_type: str = "belongs_to", fk: str | None = None) -> dict:
    return {
        "source_entity": source,
        "target_entity": target,
        "relation_type": rel_type,
        **({"foreign_key": fk} if fk else {}),
    }


class TestSingleEntity:
    """单实体 graph"""

    def test_single_entity(self):
        project = BatchCrudProject(
            project_name="test",
            entities=[_entity("order", "orders", "订单")],
        )
        graph = build_project_graph(project)

        assert graph.valid is True
        assert graph.version == GRAPH_VERSION
        assert graph.entity_count == 1
        assert graph.edge_count == 0
        assert len(graph.nodes) == 1
        assert graph.nodes[0].module == "order"
        assert graph.nodes[0].field_count == 1
        assert graph.generation_order == ["order"]
        assert len(graph.issues) == 0

    def test_to_dict(self):
        project = BatchCrudProject(
            project_name="test",
            entities=[_entity("order", "orders", "订单")],
        )
        graph = build_project_graph(project)
        d = graph.to_dict()

        assert "nodes" in d
        assert "edges" in d
        assert "generation_order" in d
        assert "version" in d


class TestChainDependency:
    """链式依赖 A → B → C"""

    def test_chain_order(self):
        project = BatchCrudProject(
            project_name="chain",
            entities=[
                _entity("order_item", "order_items", "订单明细"),
                _entity("order", "orders", "订单"),
                _entity("customer", "customers", "客户"),
            ],
            cross_relations=[
                _relation("order", "customer", "belongs_to"),
                _relation("order_item", "order", "belongs_to"),
            ],
        )
        graph = build_project_graph(project)

        assert graph.valid is True
        assert graph.entity_count == 3
        assert graph.edge_count == 2

        # 生成顺序：customer → order → order_item
        order = graph.generation_order
        assert order.index("customer") < order.index("order")
        assert order.index("order") < order.index("order_item")

    def test_chain_edges(self):
        project = BatchCrudProject(
            project_name="chain",
            entities=[
                _entity("order_item", "order_items", "订单明细"),
                _entity("order", "orders", "订单"),
                _entity("customer", "customers", "客户"),
            ],
            cross_relations=[
                _relation("order", "customer", "belongs_to"),
                _relation("order_item", "order", "belongs_to"),
            ],
        )
        graph = build_project_graph(project)

        sources = {(e.source, e.target) for e in graph.edges}
        assert ("order", "customer") in sources
        assert ("order_item", "order") in sources


class TestDiamondDependency:
    """菱形依赖 A → B, A → C, B → D, C → D"""

    def test_diamond_order(self):
        project = BatchCrudProject(
            project_name="diamond",
            entities=[
                _entity("a", "a_table", "A"),
                _entity("b", "b_table", "B"),
                _entity("c", "c_table", "C"),
                _entity("d", "d_table", "D"),
            ],
            cross_relations=[
                _relation("a", "b", "belongs_to"),
                _relation("a", "c", "belongs_to"),
                _relation("b", "d", "belongs_to"),
                _relation("c", "d", "belongs_to"),
            ],
        )
        graph = build_project_graph(project)

        assert graph.valid is True
        assert graph.entity_count == 4
        order = graph.generation_order
        # D must be first, A must be last
        assert order.index("d") < order.index("b")
        assert order.index("d") < order.index("c")
        assert order.index("b") < order.index("a")
        assert order.index("c") < order.index("a")

    def test_diamond_node_order_index(self):
        project = BatchCrudProject(
            project_name="diamond",
            entities=[
                _entity("a", "a_table", "A"),
                _entity("b", "b_table", "B"),
                _entity("c", "c_table", "C"),
                _entity("d", "d_table", "D"),
            ],
            cross_relations=[
                _relation("a", "b", "belongs_to"),
                _relation("a", "c", "belongs_to"),
                _relation("b", "d", "belongs_to"),
                _relation("c", "d", "belongs_to"),
            ],
        )
        graph = build_project_graph(project)

        node_map = {n.module: n for n in graph.nodes}
        # All nodes should have valid order_index
        for node in graph.nodes:
            assert node.order_index >= 0


class TestCycleDependency:
    """循环依赖"""

    def test_cycle_detected(self):
        project = BatchCrudProject(
            project_name="cycle",
            entities=[
                _entity("a", "a_table", "A"),
                _entity("b", "b_table", "B"),
            ],
            cross_relations=[
                _relation("a", "b", "belongs_to"),
                _relation("b", "a", "belongs_to"),
            ],
        )
        graph = build_project_graph(project)

        assert graph.valid is False
        assert len(graph.issues) > 0

        cycle_issues = [
            i for i in graph.issues
            if "cycle" in i.code.lower()
        ]
        assert len(cycle_issues) > 0
        # Should reference the involved nodes
        all_related = set()
        for ci in cycle_issues:
            all_related.update(ci.related_nodes)
        assert "a" in all_related or "b" in all_related


class TestSharedEnumsWarning:
    """shared_enums v1 warnings"""

    def test_shared_enums_warning_in_graph(self):
        project = BatchCrudProject(
            project_name="test",
            entities=[_entity("order", "orders", "订单")],
            shared_enums=[{"name": "StatusEnum", "values": [{"value": "active", "label_zh": "活跃", "label_en": "Active"}]}],
        )
        graph = build_project_graph(project)

        warning_codes = [w.code for w in graph.warnings]
        assert "shared_enums_v1" in warning_codes


class TestGraphMetadata:
    """Graph 元数据"""

    def test_project_name(self):
        project = BatchCrudProject(
            project_name="my_project",
            entities=[_entity("order", "orders", "订单")],
        )
        graph = build_project_graph(project)
        assert graph.project_name == "my_project"

    def test_edge_count(self):
        project = BatchCrudProject(
            project_name="test",
            entities=[
                _entity("a", "a_table", "A"),
                _entity("b", "b_table", "B"),
            ],
            cross_relations=[
                _relation("a", "b", "belongs_to"),
            ],
        )
        graph = build_project_graph(project)
        assert graph.edge_count == 1

    def test_no_duplicate_edges(self):
        """cross_relations 和 dep graph 不重复"""
        project = BatchCrudProject(
            project_name="test",
            entities=[
                _entity("a", "a_table", "A"),
                _entity("b", "b_table", "B"),
            ],
            cross_relations=[
                _relation("a", "b", "belongs_to"),
            ],
        )
        graph = build_project_graph(project)
        # Should only have 1 edge, not 2
        ab_edges = [
            e for e in graph.edges
            if e.source == "a" and e.target == "b"
        ]
        assert len(ab_edges) == 1
