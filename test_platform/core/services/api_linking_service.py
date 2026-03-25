from typing import Any, Dict, List, Set


class ApiLinkingService:
    """负责构建结构化接口用例的关联编排计划。"""

    def build_link_plan(self, cases: List[Dict[str, Any]], scenes: List[Dict[str, Any]]) -> Dict[str, Any]:
        case_order: List[str] = []
        case_index: Dict[str, Dict[str, Any]] = {}
        case_dependencies: Dict[str, List[str]] = {}
        extract_variables: Dict[str, List[str]] = {}
        warnings: List[str] = []

        for raw_case in cases:
            if not isinstance(raw_case, dict):
                continue
            case_id = str(raw_case.get("case_id") or "").strip()
            if not case_id or case_id in case_index:
                continue
            case_order.append(case_id)
            case_index[case_id] = raw_case

        for case_id in case_order:
            raw_case = case_index[case_id]
            resolved_dependencies: List[str] = []
            raw_dependencies = raw_case.get("depends_on") if isinstance(raw_case.get("depends_on"), list) else []
            for dependency_id in raw_dependencies:
                normalized_dependency = str(dependency_id or "").strip()
                if not normalized_dependency:
                    continue
                if normalized_dependency not in case_index:
                    warnings.append(f"用例 {case_id} 存在未定义依赖：{normalized_dependency}")
                    continue
                resolved_dependencies.append(normalized_dependency)
            case_dependencies[case_id] = resolved_dependencies

            raw_extract = raw_case.get("extract") if isinstance(raw_case.get("extract"), list) else []
            for rule in raw_extract:
                if not isinstance(rule, dict):
                    continue
                variable_name = str(rule.get("name") or "").strip()
                if not variable_name:
                    continue
                extract_variables.setdefault(variable_name, []).append(case_id)

        for variable_name, provider_cases in extract_variables.items():
            if len(provider_cases) > 1:
                warnings.append(
                    f"提取变量 {variable_name} 被多个用例重复写入：{', '.join(provider_cases)}"
                )

        scene_orders: List[Dict[str, Any]] = []
        scene_case_ids: Set[str] = set()
        for raw_scene in scenes:
            if not isinstance(raw_scene, dict):
                continue
            scene_id = str(raw_scene.get("scene_id") or "").strip()
            raw_steps = raw_scene.get("steps") if isinstance(raw_scene.get("steps"), list) else []
            scene_steps = []
            for step in raw_steps:
                step_id = str(step or "").strip()
                if not step_id:
                    continue
                if step_id not in case_index:
                    warnings.append(f"场景 {scene_id or '未命名场景'} 引用了未定义用例：{step_id}")
                    continue
                scene_steps.append(step_id)

            ordered_steps = self._topological_sort(scene_steps, case_dependencies, warnings)
            if scene_id:
                scene_orders.append(
                    {
                        "scene_id": scene_id,
                        "ordered_steps": ordered_steps,
                    }
                )
            scene_case_ids.update(ordered_steps)

        standalone_case_ids = [
            case_id
            for case_id in self._topological_sort(case_order, case_dependencies, warnings)
            if case_id not in scene_case_ids
        ]

        ordered_case_ids: List[str] = []
        seen_case_ids: Set[str] = set()
        for scene_order_item in scene_orders:
            for case_id in scene_order_item.get("ordered_steps", []):
                if case_id in seen_case_ids:
                    continue
                seen_case_ids.add(case_id)
                ordered_case_ids.append(case_id)
        for case_id in standalone_case_ids:
            if case_id in seen_case_ids:
                continue
            seen_case_ids.add(case_id)
            ordered_case_ids.append(case_id)

        return {
            "ordered_case_ids": ordered_case_ids,
            "standalone_case_ids": standalone_case_ids,
            "scene_orders": scene_orders,
            "case_dependencies": case_dependencies,
            "extract_variables": extract_variables,
            "warnings": list(dict.fromkeys(warnings)),
        }

    def _topological_sort(
        self,
        node_ids: List[str],
        dependency_map: Dict[str, List[str]],
        warnings: List[str],
    ) -> List[str]:
        ordered: List[str] = []
        visited: Set[str] = set()
        visiting: Set[str] = set()
        scoped_nodes = [node_id for node_id in node_ids if str(node_id or "").strip()]
        scoped_node_set = set(scoped_nodes)

        def visit(node_id: str) -> None:
            if node_id in visited:
                return
            if node_id in visiting:
                warnings.append(f"检测到循环依赖：{node_id}")
                return

            visiting.add(node_id)
            for dependency_id in dependency_map.get(node_id, []):
                if dependency_id not in scoped_node_set:
                    continue
                visit(dependency_id)
            visiting.remove(node_id)
            visited.add(node_id)
            ordered.append(node_id)

        for node_id in scoped_nodes:
            visit(node_id)

        return ordered
