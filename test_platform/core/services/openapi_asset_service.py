import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple, cast


class OpenApiAssetService:
    """负责将 OpenAPI JSON 解析为统一接口资产。"""

    RESOURCE_ACTION_SEGMENTS = {
        "adminlist",
        "list",
        "page",
        "query",
        "search",
        "detail",
        "info",
        "get",
        "add",
        "create",
        "save",
        "insert",
        "update",
        "edit",
        "modify",
        "delete",
        "remove",
        "updatestatus",
        "status",
        "enable",
        "disable",
        "publish",
        "offline",
        "online",
    }
    LOOKUP_FIELD_PRIORITY = ("title", "businessId", "jumpUrl", "name", "code")
    EXCLUDED_LOOKUP_FIELDS = {"id", "ids", "page", "size", "limit", "offset", "orderSql", "status"}

    def parse_text(self, raw_text: str, file_name: str = "") -> Dict[str, Any]:
        payload = json.loads(str(raw_text or "").strip())
        if not isinstance(payload, dict):
            raise ValueError("OpenAPI 文档必须是 JSON 对象")
        return self.build_asset(cast(Dict[str, Any], payload), file_name=file_name)

    def build_asset(self, spec: Dict[str, Any], file_name: str = "") -> Dict[str, Any]:
        info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
        operations: List[Dict[str, Any]] = []
        resource_map: Dict[str, Dict[str, Any]] = {}
        header_fields: Set[str] = set()
        cookie_fields: Set[str] = set()
        warnings: List[str] = []

        paths = spec.get("paths")
        if not isinstance(paths, dict):
            raise ValueError("OpenAPI 文档缺少有效的 paths 定义")

        for raw_path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            resource_key = self._infer_resource_key(str(raw_path or ""))
            tag_name = self._extract_primary_tag(path_item)
            resource_entry = resource_map.setdefault(
                resource_key,
                {
                    "resource_key": resource_key,
                    "tag": tag_name,
                    "lookup_fields": [],
                    "operation_ids": [],
                    "operation_categories": [],
                },
            )
            if not resource_entry.get("tag") and tag_name:
                resource_entry["tag"] = tag_name

            shared_parameters = path_item.get("parameters") if isinstance(path_item.get("parameters"), list) else []
            for raw_method, operation in path_item.items():
                method = str(raw_method or "").lower()
                if method not in {"get", "post", "put", "delete", "patch", "options", "head"}:
                    continue
                if not isinstance(operation, dict):
                    continue

                operation_id = f"{method.upper()} {str(raw_path or '').strip()}"
                category = self._classify_operation(str(raw_path or ""), method, str(operation.get("summary") or ""))
                request_schema = self._resolve_request_schema(spec, operation)
                response_schema = self._resolve_response_schema(spec, operation)
                request_field_specs = self._build_request_field_specs(spec, request_schema)
                request_fields = list(request_field_specs.keys())
                response_extract_paths = self._detect_response_extract_paths(spec, response_schema)
                auth_headers, auth_cookies = self._collect_operation_auth_fields(spec, shared_parameters, operation)

                header_fields.update(auth_headers)
                cookie_fields.update(auth_cookies)
                if category == "create":
                    resource_entry["lookup_fields"] = self._build_lookup_fields(request_fields)

                operation_data = {
                    "operation_id": operation_id,
                    "path": str(raw_path or "").strip(),
                    "method": method.upper(),
                    "summary": str(operation.get("summary") or operation.get("operationId") or "").strip(),
                    "tags": [str(tag).strip() for tag in operation.get("tags", []) if str(tag).strip()] if isinstance(operation.get("tags"), list) else [],
                    "category": category,
                    "resource_key": resource_key,
                    "request_schema_name": self._extract_schema_name(request_schema),
                    "response_schema_name": self._extract_schema_name(response_schema),
                    "request_fields": request_fields,
                    "request_field_specs": request_field_specs,
                    "response_extract_paths": response_extract_paths,
                    "auth_headers": auth_headers,
                    "auth_cookies": auth_cookies,
                }
                operations.append(operation_data)
                resource_entry["operation_ids"].append(operation_id)
                resource_entry["operation_categories"].append(category)

        security_headers = self._collect_security_header_names(spec)
        header_fields.update(security_headers)

        resources = list(resource_map.values())
        resources.sort(key=lambda item: str(item.get("resource_key") or ""))
        operations.sort(key=lambda item: (str(item.get("resource_key") or ""), str(item.get("path") or ""), str(item.get("method") or "")))

        for resource in resources:
            if not resource.get("lookup_fields"):
                resource["lookup_fields"] = []
            if "create" in resource.get("operation_categories", []) and "list" not in resource.get("operation_categories", []):
                warnings.append(f"资源组 {resource['resource_key']} 缺少可用于回查的 list 接口，后续关联能力会受限。")

        return {
            "file_name": file_name,
            "title": str((info or {}).get("title") or file_name or "未命名 OpenAPI 文档").strip(),
            "version": str((info or {}).get("version") or "").strip(),
            "openapi_version": str(spec.get("openapi") or spec.get("swagger") or "").strip(),
            "servers": self._normalize_servers(spec.get("servers")),
            "auth_profile": {
                "required_headers": sorted(header_fields),
                "required_cookies": sorted(cookie_fields),
            },
            "resources": resources,
            "operations": operations,
            "warnings": warnings,
        }

    def _normalize_servers(self, servers: Any) -> List[Dict[str, str]]:
        normalized: List[Dict[str, str]] = []
        if not isinstance(servers, list):
            return normalized
        for server in servers:
            if not isinstance(server, dict):
                continue
            url = str(server.get("url") or "").strip()
            if not url:
                continue
            normalized.append(
                {
                    "url": url,
                    "description": str(server.get("description") or "").strip(),
                }
            )
        return normalized

    def _extract_primary_tag(self, path_item: Dict[str, Any]) -> str:
        parameters = path_item.get("parameters")
        if isinstance(parameters, list):
            pass

        for raw_method, operation in path_item.items():
            if str(raw_method or "").lower() not in {"get", "post", "put", "delete", "patch", "options", "head"}:
                continue
            if not isinstance(operation, dict):
                continue
            tags = operation.get("tags")
            if isinstance(tags, list):
                for tag in tags:
                    tag_name = str(tag or "").strip()
                    if tag_name:
                        return tag_name
        return ""

    def _infer_resource_key(self, path: str) -> str:
        parts = [part for part in str(path or "").split("/") if part]
        if not parts:
            return "default"

        last_part = parts[-1]
        normalized_last = re.sub(r"[^a-z0-9]", "", last_part.lower())
        if normalized_last in self.RESOURCE_ACTION_SEGMENTS and len(parts) >= 2:
            return parts[-2]
        return last_part

    def _classify_operation(self, path: str, method: str, summary: str) -> str:
        normalized = f"{method} {path} {summary}".lower()
        compact = re.sub(r"[^a-z0-9]", "", normalized)
        if any(token in compact for token in ("login", "logout", "token", "auth")):
            return "auth"
        if any(token in compact for token in ("updatestatus", "enable", "disable", "publish", "offline", "online")):
            return "status"
        if any(token in compact for token in ("delete", "remove")):
            return "delete"
        if any(token in compact for token in ("add", "create", "save", "insert")):
            return "create"
        if any(token in compact for token in ("update", "edit", "modify")):
            return "update"
        if any(token in compact for token in ("adminlist", "list", "page", "query", "search")):
            return "list"
        if any(token in compact for token in ("detail", "info", "view")):
            return "detail"
        return "unknown"

    def _collect_operation_auth_fields(
        self,
        spec: Dict[str, Any],
        shared_parameters: List[Any],
        operation: Dict[str, Any],
    ) -> Tuple[List[str], List[str]]:
        raw_parameters: List[Any] = []
        raw_parameters.extend(shared_parameters)
        if isinstance(operation.get("parameters"), list):
            raw_parameters.extend(cast(List[Any], operation.get("parameters")))

        headers: Set[str] = set()
        cookies: Set[str] = set()
        for parameter in raw_parameters:
            resolved = self._resolve_schema_ref(spec, parameter)
            if not isinstance(resolved, dict):
                continue
            name = str(resolved.get("name") or "").strip()
            location = str(resolved.get("in") or "").strip().lower()
            if not name:
                continue
            if location == "header":
                headers.add(name)
            elif location == "cookie":
                cookies.add(name)

        return sorted(headers), sorted(cookies)

    def _collect_security_header_names(self, spec: Dict[str, Any]) -> List[str]:
        security_schemes = cast(Dict[str, Any], cast(Dict[str, Any], spec.get("components") or {}).get("securitySchemes") or {})
        headers: Set[str] = set()
        for scheme in security_schemes.values():
            if not isinstance(scheme, dict):
                continue
            if str(scheme.get("type") or "").strip() == "apiKey" and str(scheme.get("in") or "").strip() == "header":
                name = str(scheme.get("name") or "").strip()
                if name:
                    headers.add(name)
        return sorted(headers)

    def _resolve_request_schema(self, spec: Dict[str, Any], operation: Dict[str, Any]) -> Dict[str, Any]:
        request_body = self._resolve_schema_ref(spec, operation.get("requestBody"))
        if not isinstance(request_body, dict):
            return {}
        content = request_body.get("content")
        if not isinstance(content, dict):
            return {}
        for media_type in ("application/json", "application/*+json"):
            media_payload = content.get(media_type)
            if isinstance(media_payload, dict):
                schema = self._resolve_schema_ref(spec, media_payload.get("schema"))
                if isinstance(schema, dict):
                    return schema
        first_item = next(iter(content.values()), None)
        if isinstance(first_item, dict):
            schema = self._resolve_schema_ref(spec, first_item.get("schema"))
            if isinstance(schema, dict):
                return schema
        return {}

    def _resolve_response_schema(self, spec: Dict[str, Any], operation: Dict[str, Any]) -> Dict[str, Any]:
        responses = operation.get("responses")
        if not isinstance(responses, dict):
            return {}
        preferred_response = responses.get("200") or next(iter(responses.values()), None)
        if not isinstance(preferred_response, dict):
            return {}
        content = preferred_response.get("content")
        if not isinstance(content, dict):
            return {}
        media_payload = content.get("application/json") or next(iter(content.values()), None)
        if not isinstance(media_payload, dict):
            return {}
        schema = self._resolve_schema_ref(spec, media_payload.get("schema"))
        return schema if isinstance(schema, dict) else {}

    def _build_lookup_fields(self, request_fields: List[str]) -> List[str]:
        request_field_set = set(request_fields)
        ordered_fields = [field for field in self.LOOKUP_FIELD_PRIORITY if field in request_field_set]
        for field in request_fields:
            if field in ordered_fields or field in self.EXCLUDED_LOOKUP_FIELDS:
                continue
            ordered_fields.append(field)
        return ordered_fields[:3]

    def _build_request_field_specs(self, spec: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        properties = self._get_schema_properties(spec, schema)
        result: Dict[str, Any] = {}
        for field_name, field_schema in properties.items():
            resolved_schema = self._resolve_schema_ref(spec, field_schema)
            if not isinstance(resolved_schema, dict):
                continue
            field_spec: Dict[str, Any] = {}
            field_type = str(resolved_schema.get("type") or "").strip()
            if field_type:
                field_spec["type"] = field_type
            if resolved_schema.get("default") is not None:
                field_spec["default"] = resolved_schema.get("default")
            if field_type == "array":
                items_schema = self._resolve_schema_ref(spec, resolved_schema.get("items"))
                if isinstance(items_schema, dict):
                    item_type = str(items_schema.get("type") or "").strip()
                    if item_type:
                        field_spec["items"] = {"type": item_type}
            result[str(field_name)] = field_spec
        return result

    def _get_schema_properties(self, spec: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        resolved = self._resolve_schema_ref(spec, schema)
        if not isinstance(resolved, dict):
            return {}
        properties = resolved.get("properties")
        return cast(Dict[str, Any], properties) if isinstance(properties, dict) else {}

    def _detect_response_extract_paths(self, spec: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        resolved = self._resolve_schema_ref(spec, schema)
        if not isinstance(resolved, dict):
            return []

        paths: List[str] = []
        top_properties = self._get_schema_properties(spec, resolved)
        if "id" in top_properties:
            paths.append("response.id")

        data_schema = self._resolve_schema_ref(spec, top_properties.get("data"))
        if isinstance(data_schema, dict):
            data_properties = self._get_schema_properties(spec, data_schema)
            if "id" in data_properties:
                paths.append("response.data.id")
            ids_schema = self._resolve_schema_ref(spec, data_properties.get("ids"))
            if isinstance(ids_schema, dict) and str(ids_schema.get("type") or "").strip() == "array":
                paths.append("response.data.ids[0]")

        return paths

    def _extract_schema_name(self, schema: Dict[str, Any]) -> str:
        ref = str(schema.get("$ref") or "").strip()
        if ref.startswith("#/components/schemas/"):
            return ref.split("/")[-1]
        return str(schema.get("title") or "").strip()

    def _resolve_schema_ref(self, spec: Dict[str, Any], node: Any) -> Any:
        if not isinstance(node, dict):
            return node

        ref = str(node.get("$ref") or "").strip()
        if not ref.startswith("#/"):
            return node

        current: Any = spec
        for part in ref[2:].split("/"):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return node
        return current
