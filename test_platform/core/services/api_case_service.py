from typing import Any, Dict, List, Optional


class ApiCaseService:
    """根据 OpenAPI 解析资产生成结构化接口测试用例。"""

    DIRECT_ID_PATHS = (
        "response.data.id",
        "response.data.ids[0]",
        "response.result.id",
        "response.result.ids[0]",
    )

    def build_suite(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        resources = asset.get("resources") if isinstance(asset.get("resources"), list) else []
        operations = asset.get("operations") if isinstance(asset.get("operations"), list) else []
        warnings = list(asset.get("warnings") or []) if isinstance(asset.get("warnings"), list) else []

        operations_by_resource: Dict[str, List[Dict[str, Any]]] = {}
        for operation in operations:
            if not isinstance(operation, dict):
                continue
            resource_key = str(operation.get("resource_key") or "").strip()
            if not resource_key:
                continue
            operations_by_resource.setdefault(resource_key, []).append(operation)

        cases: List[Dict[str, Any]] = []
        scenes: List[Dict[str, Any]] = []
        covered_operation_ids = set()

        for resource in resources:
            if not isinstance(resource, dict):
                continue
            resource_key = str(resource.get("resource_key") or "").strip()
            if not resource_key:
                continue

            resource_operations = operations_by_resource.get(resource_key, [])
            resource_result = self._build_resource_suite(resource, resource_operations)
            cases.extend(resource_result["cases"])
            scenes.extend(resource_result["scenes"])
            warnings.extend(resource_result["warnings"])
            covered_operation_ids.update(resource_result["covered_operation_ids"])

        for operation in operations:
            if not isinstance(operation, dict):
                continue
            operation_id = str(operation.get("operation_id") or "").strip()
            if not operation_id or operation_id in covered_operation_ids:
                continue
            cases.append(self._build_success_case(operation))

        return {
            "summary": f"已识别 {len(operations)} 个接口，生成 {len(cases)} 条结构化用例和 {len(scenes)} 个关联场景。",
            "cases": cases,
            "scenes": scenes,
            "warnings": list(dict.fromkeys([str(item).strip() for item in warnings if str(item).strip()])),
        }

    def _build_resource_suite(self, resource: Dict[str, Any], operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        category_map: Dict[str, Dict[str, Any]] = {}
        warnings: List[str] = []
        cases: List[Dict[str, Any]] = []
        scene_steps: List[str] = []
        covered_operation_ids = set()

        for operation in operations:
            if not isinstance(operation, dict):
                continue
            category = str(operation.get("category") or "unknown").strip() or "unknown"
            category_map.setdefault(category, operation)

        resource_key = str(resource.get("resource_key") or "").strip()
        resource_name = str(resource.get("tag") or resource_key or "未命名资源").strip()
        lookup_fields = resource.get("lookup_fields") if isinstance(resource.get("lookup_fields"), list) else []

        create_operation = category_map.get("create")
        list_operation = category_map.get("list")
        update_operation = category_map.get("update")
        status_operation = category_map.get("status")
        delete_operation = category_map.get("delete")

        latest_dependency_case_id = ""
        resource_id_provider_case_id = ""

        if create_operation:
            create_case = self._build_success_case(
                create_operation,
                title=f"新增{resource_name}成功",
            )
            direct_id_path = self._pick_direct_id_path(create_operation)
            if direct_id_path:
                create_case["extract"] = [
                    {
                        "name": "resource_id",
                        "from": "response",
                        "pick": direct_id_path,
                    }
                ]
                resource_id_provider_case_id = create_case["case_id"]

            cases.append(create_case)
            scene_steps.append(create_case["case_id"])
            covered_operation_ids.add(create_case["operation_id"])
            latest_dependency_case_id = create_case["case_id"]

        if create_operation and not resource_id_provider_case_id:
            if list_operation:
                lookup_case = self._build_lookup_case(
                    resource=resource,
                    operation=list_operation,
                    depends_on=[latest_dependency_case_id] if latest_dependency_case_id else [],
                )
                cases.append(lookup_case)
                scene_steps.append(lookup_case["case_id"])
                covered_operation_ids.add(lookup_case["operation_id"])
                latest_dependency_case_id = lookup_case["case_id"]
                resource_id_provider_case_id = lookup_case["case_id"]
            else:
                warnings.append(f"资源组 {resource_key} 缺少 list 接口，新增后无法自动回查对象。")

        if update_operation:
            update_case = self._build_success_case(
                update_operation,
                title=f"更新{resource_name}成功",
                depends_on=[resource_id_provider_case_id] if resource_id_provider_case_id else [],
                assertions=["响应状态码为 200", "业务返回码为成功"],
            )
            cases.append(update_case)
            scene_steps.append(update_case["case_id"])
            covered_operation_ids.add(update_case["operation_id"])
            latest_dependency_case_id = update_case["case_id"]

        if status_operation:
            status_case = self._build_success_case(
                status_operation,
                title=f"更新{resource_name}状态成功",
                depends_on=[latest_dependency_case_id] if latest_dependency_case_id else [],
                assertions=["响应状态码为 200", "状态变更成功"],
            )
            cases.append(status_case)
            scene_steps.append(status_case["case_id"])
            covered_operation_ids.add(status_case["operation_id"])
            latest_dependency_case_id = status_case["case_id"]

        if delete_operation:
            delete_case = self._build_success_case(
                delete_operation,
                title=f"删除{resource_name}成功",
                depends_on=[latest_dependency_case_id] if latest_dependency_case_id else [],
                assertions=["响应状态码为 200", "删除操作成功"],
            )
            cases.append(delete_case)
            scene_steps.append(delete_case["case_id"])
            covered_operation_ids.add(delete_case["operation_id"])
            latest_dependency_case_id = delete_case["case_id"]

        if delete_operation and list_operation:
            verify_case = {
                "case_id": f"{resource_key}_verify_deleted",
                "title": f"校验{resource_name}已删除",
                "operation_id": str(list_operation.get("operation_id") or "").strip(),
                "resource_key": resource_key,
                "category": "list",
                "priority": "P1",
                "depends_on": [latest_dependency_case_id] if latest_dependency_case_id else [],
                "extract": [],
                "assertions": [
                    "列表结果中不再包含目标对象",
                ],
            }
            cases.append(verify_case)
            scene_steps.append(verify_case["case_id"])
            covered_operation_ids.add(verify_case["operation_id"])

        scenes: List[Dict[str, Any]] = []
        if len(scene_steps) >= 2:
            scenes.append(
                {
                    "scene_id": f"{resource_key}_crud_flow",
                    "title": f"{resource_name} CRUD 主链路",
                    "description": f"围绕 {resource_name} 的新增、回查、更新、状态流转与删除校验主流程。",
                    "steps": scene_steps,
                }
            )

        if create_operation and not lookup_fields and list_operation and not resource_id_provider_case_id:
            warnings.append(f"资源组 {resource_key} 缺少稳定回查字段，可能需要人工指定对象定位条件。")

        return {
            "cases": cases,
            "scenes": scenes,
            "warnings": warnings,
            "covered_operation_ids": covered_operation_ids,
        }

    def _build_lookup_case(
        self,
        resource: Dict[str, Any],
        operation: Dict[str, Any],
        depends_on: List[str],
    ) -> Dict[str, Any]:
        resource_key = str(resource.get("resource_key") or "").strip()
        resource_name = str(resource.get("tag") or resource_key or "未命名资源").strip()
        return {
            "case_id": f"{resource_key}_lookup_after_add",
            "title": f"新增后回查{resource_name}记录",
            "operation_id": str(operation.get("operation_id") or "").strip(),
            "resource_key": resource_key,
            "category": "list",
            "priority": "P1",
            "depends_on": depends_on,
            "extract": [
                {
                    "name": "resource_id",
                    "from": "lookup",
                    "pick": "response.data.list[0].id",
                }
            ],
            "assertions": [
                "列表结果中能命中新创建对象",
            ],
        }

    def _build_success_case(
        self,
        operation: Dict[str, Any],
        title: str = "",
        depends_on: Optional[List[str]] = None,
        assertions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        resource_key = str(operation.get("resource_key") or "default").strip() or "default"
        action_name = self._extract_action_name(operation)
        action_label = title or f"{action_name} 成功"
        return {
            "case_id": f"{resource_key}_{action_name}_success",
            "title": action_label,
            "operation_id": str(operation.get("operation_id") or "").strip(),
            "resource_key": resource_key,
            "category": str(operation.get("category") or "unknown").strip() or "unknown",
            "priority": "P1",
            "depends_on": [item for item in (depends_on or []) if str(item).strip()],
            "extract": [],
            "assertions": assertions or ["响应状态码为 200", "业务返回码为成功"],
        }

    def _extract_action_name(self, operation: Dict[str, Any]) -> str:
        summary = str(operation.get("summary") or "").strip()
        if summary:
            return summary.replace(" ", "")

        path = str(operation.get("path") or "").strip()
        parts = [part for part in path.split("/") if part]
        if parts:
            return parts[-1]
        return str(operation.get("category") or "unknown").strip() or "unknown"

    def _pick_direct_id_path(self, operation: Dict[str, Any]) -> str:
        response_extract_paths = operation.get("response_extract_paths")
        if not isinstance(response_extract_paths, list):
            return ""

        normalized_paths = [str(item).strip() for item in response_extract_paths if str(item).strip()]
        for candidate in self.DIRECT_ID_PATHS:
            if candidate in normalized_paths:
                return candidate
        return ""
