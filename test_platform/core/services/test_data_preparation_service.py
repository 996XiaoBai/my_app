import html
import quopri
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from test_platform.core.services.result_contracts import build_test_data_pack


@dataclass
class TestDataColumn:
    __test__ = False

    name: str
    sql_type: str = ""
    description: str = ""
    required: bool = False
    default: str = ""
    primary_key: bool = False
    auto_increment: bool = False


@dataclass
class TestDataTable:
    __test__ = False

    name: str
    display_name: str
    description: str = ""
    columns: List[TestDataColumn] = field(default_factory=list)
    source: str = "ddl"


@dataclass
class TestDataScenario:
    __test__ = False

    name: str
    tables: List[str]
    select_sql: str
    insert_sql: str
    update_sql: str
    delete_sql: str


class TestDataPreparationService:
    CREATE_TABLE_PATTERN = re.compile(
        r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?P<name>`?[A-Za-z0-9_$.]+`?(?:\.`?[A-Za-z0-9_$.]+`?)?)",
        re.IGNORECASE,
    )
    COMMENT_PATTERN = re.compile(r"\bcomment\s*(?:=)?\s*'([^']*)'", re.IGNORECASE)
    DEFAULT_PATTERN = re.compile(r"\bdefault\s+((?:'[^']*')|(?:\"[^\"]*\")|(?:[^\s,]+))", re.IGNORECASE)
    DATA_URI_PATTERN = re.compile(r"data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+", re.IGNORECASE)
    MIME_HEADER_PATTERN = re.compile(
        r"^(?:Date|Message-ID|Subject|MIME-Version|Content-Type|Content-Transfer-Encoding|Content-Location):.*$",
        re.IGNORECASE | re.MULTILINE,
    )
    MIME_BOUNDARY_PATTERN = re.compile(r"^-{4,}=_Part_[^\n]+$", re.MULTILINE)
    HEADER_ALIAS_MAP = {
        "name": {"字段", "字段名", "列名", "column", "column name", "field", "field name"},
        "type": {"类型", "字段类型", "数据类型", "type", "data type"},
        "description": {"说明", "描述", "备注", "注释", "comment", "desc", "description"},
        "required": {"必填", "是否必填", "nullable", "是否为空", "not null", "allow null"},
        "default": {"默认值", "default"},
        "primary_key": {"主键", "key", "索引", "pk"},
    }
    KEYWORD_LABELS = {
        "goods": "商品",
        "product": "商品",
        "item": "条目",
        "live": "直播",
        "room": "直播间",
        "record": "记录",
        "user": "用户",
        "account": "账号",
        "order": "订单",
        "task": "任务",
        "config": "配置",
        "activity": "活动",
        "coupon": "优惠券",
        "detail": "明细",
        "relation": "关系",
        "message": "消息",
        "tag": "标签",
        "status": "状态",
        "schedule": "排期",
        # --- 扩充词典：常见业务实体 ---
        "settlement": "结算",
        "commission": "佣金",
        "logistics": "物流",
        "payment": "支付",
        "refund": "退款",
        "stock": "库存",
        "inventory": "库存",
        "category": "分类",
        "shop": "店铺",
        "store": "门店",
        "merchant": "商户",
        "address": "地址",
        "delivery": "配送",
        "review": "审核",
        "audit": "审计",
        "log": "日志",
        "notify": "通知",
        "notification": "通知",
        "comment": "评论",
        "feedback": "反馈",
        "report": "报告",
        "channel": "渠道",
        "promotion": "推广",
        "member": "会员",
        "role": "角色",
        "permission": "权限",
        "template": "模板",
        "batch": "批次",
        "flow": "流水",
        "bill": "账单",
        "contract": "合同",
        "verify": "核验",
        "sign": "签约",
        "withdraw": "提现",
    }
    # 表名推断时排除的常见字段名后缀
    _FIELD_NAME_SUFFIXES = {
        "_at", "_by", "_id", "_no", "_time", "_date",
        "_name", "_type", "_code", "_status", "_key",
        "_url", "_path", "_flag", "_count", "_num",
    }
    # UPDATE 语句中优先选择的有测试价值的字段关键词
    _HIGH_VALUE_UPDATE_KEYWORDS = {
        "status", "state", "name", "title", "amount",
        "price", "remark", "desc", "level", "score",
        "count", "quantity", "balance",
    }

    def prepare_result(
        self,
        document_name: str,
        raw_text: str,
        extra_prompt: str = "",
        status_callback=None,
    ) -> Dict[str, Any]:
        source_text = str(raw_text or "")
        if status_callback:
            status_callback("🧹 正在清洗技术文档噪音...")
        cleaned_text = self.clean_document(source_text)

        if status_callback:
            status_callback("🧩 正在识别表结构与字段定义...")
        tables, warnings = self.extract_tables(cleaned_text)
        if not tables and cleaned_text != source_text:
            fallback_tables, fallback_warnings = self.extract_tables(source_text)
            if fallback_tables:
                tables = fallback_tables
                warnings.append("清洗文本未识别到表结构，已回退到原始文本继续抽取。")
            warnings.extend(
                warning for warning in fallback_warnings if warning not in warnings
            )

        if status_callback:
            status_callback("🧠 正在生成按表 SQL 和场景 SQL...")
        scenarios = self.build_scenarios(tables, extra_prompt=extra_prompt)

        if not tables:
            warnings.append("未识别到可生成 SQL 的表结构，请优先提供包含建表语句或字段表格的技术文档。")
        if tables and not scenarios:
            warnings.append("已识别表结构，但未生成额外场景 SQL，当前结果仅保留按表模板。")

        summary = self._build_summary(document_name, tables, scenarios)
        return build_test_data_pack(
            raw_tables=[self._serialize_table(table) for table in tables],
            raw_scenarios=[self._serialize_scenario(scenario) for scenario in scenarios],
            warnings=warnings,
            summary=summary,
            document_name=document_name,
        )

    def build_markdown(
        self,
        document_name: str,
        raw_text: str,
        extra_prompt: str = "",
        status_callback=None,
    ) -> str:
        payload = self.prepare_result(
            document_name=document_name,
            raw_text=raw_text,
            extra_prompt=extra_prompt,
            status_callback=status_callback,
        )
        return str(payload.get("markdown") or "")

    def clean_document(self, raw_text: str) -> str:
        text = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
        if not text:
            return ""

        if "quoted-printable" in text.lower() or "=3D" in text or "=E" in text:
            try:
                decoded = quopri.decodestring(text.encode("utf-8", errors="ignore")).decode("utf-8", errors="ignore")
                if decoded.strip():
                    text = decoded
            except Exception:
                pass

        text = html.unescape(text)
        text = self.MIME_HEADER_PATTERN.sub("", text)
        text = self.MIME_BOUNDARY_PATTERN.sub("", text)
        text = self.DATA_URI_PATTERN.sub(" ", text)
        text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
        text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</(?:p|div|section|article|li|ul|ol|h[1-6]|pre|code)>", "\n", text)
        text = re.sub(r"(?i)</(?:table|tr)>", "\n", text)
        text = re.sub(r"(?i)</t[dh]>", " | ", text)
        text = re.sub(r"(?i)<[^>]+>", " ", text)
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    def extract_tables(self, text: str) -> Tuple[List[TestDataTable], List[str]]:
        warnings: List[str] = []
        ddl_tables = self._extract_create_table_schemas(text)
        markdown_tables, markdown_warnings = self._extract_markdown_table_schemas(text)
        warnings.extend(markdown_warnings)
        merged_tables = self._merge_tables(ddl_tables, markdown_tables)
        return merged_tables, warnings

    def build_scenarios(self, tables: List[TestDataTable], extra_prompt: str = "") -> List[TestDataScenario]:
        scenarios: List[TestDataScenario] = []
        prompt_hint = str(extra_prompt or "").strip()
        for table in tables:
            label = table.display_name or table.description or table.name
            if prompt_hint:
                scene_name = f"{label}数据准备（{prompt_hint[:12]}）"
            else:
                scene_name = f"查询与插入{label}"
            scenarios.append(
                TestDataScenario(
                    name=scene_name,
                    tables=[table.name],
                    select_sql=self._build_select_sql(table),
                    insert_sql=self._build_insert_sql(table),
                    update_sql=self._build_update_sql(table),
                    delete_sql=self._build_delete_sql(table),
                )
            )
        return scenarios

    def _extract_create_table_schemas(self, text: str) -> List[TestDataTable]:
        tables: List[TestDataTable] = []
        matches = list(self.CREATE_TABLE_PATTERN.finditer(text))
        for index, match in enumerate(matches):
            table_name = self._normalize_identifier(match.group("name"))
            opening_index = text.find("(", match.end())
            if opening_index == -1:
                continue
            closing_index = self._find_matching_parenthesis(text, opening_index)
            if closing_index == -1:
                continue

            next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            tail = text[closing_index + 1:next_start]
            statement_end = tail.find(";")
            statement_tail = tail if statement_end == -1 else tail[:statement_end]
            columns_block = text[opening_index + 1:closing_index]
            columns = self._parse_create_table_columns(columns_block)
            table_comment = self._extract_comment(statement_tail)
            tables.append(
                TestDataTable(
                    name=table_name,
                    display_name=self._build_display_name(table_name, table_comment),
                    description=table_comment,
                    columns=columns,
                    source="ddl",
                )
            )
        return tables

    def _extract_markdown_table_schemas(self, text: str) -> Tuple[List[TestDataTable], List[str]]:
        lines = text.splitlines()
        groups: List[Tuple[int, List[str]]] = []
        current_group: List[str] = []
        start_index = -1
        warnings: List[str] = []

        for line_index, line in enumerate(lines):
            if line.count("|") >= 2:
                if not current_group:
                    start_index = line_index
                current_group.append(line)
                continue
            if len(current_group) >= 2:
                groups.append((start_index, current_group[:]))
            current_group = []
            start_index = -1

        if len(current_group) >= 2:
            groups.append((start_index, current_group[:]))

        tables: List[TestDataTable] = []
        for group_start, raw_group in groups:
            rows = [self._split_markdown_row(row) for row in raw_group]
            rows = [row for row in rows if row]
            if len(rows) < 2:
                continue

            header = rows[0]
            data_rows = rows[2:] if len(rows) >= 3 and self._is_markdown_separator(rows[1]) else rows[1:]
            column_index_map = self._match_header_indexes(header)
            if "name" not in column_index_map:
                continue
            if "type" not in column_index_map and "description" not in column_index_map:
                continue

            context_lines = lines[max(0, group_start - 3):group_start]
            table_name = self._infer_table_name_from_context(context_lines)
            if not table_name:
                warnings.append("发现字段表格，但未能可靠识别表名，已跳过该表格。")
                continue

            description_line = next((line.strip() for line in reversed(context_lines) if line.strip()), "")
            columns: List[TestDataColumn] = []
            for row in data_rows:
                if all(not cell.strip() for cell in row):
                    continue
                field_name = self._get_markdown_value(row, column_index_map.get("name"))
                if not field_name:
                    continue
                sql_type = self._get_markdown_value(row, column_index_map.get("type"))
                description = self._get_markdown_value(row, column_index_map.get("description"))
                default_value = self._get_markdown_value(row, column_index_map.get("default"))
                required_text = self._get_markdown_value(row, column_index_map.get("required"))
                key_text = self._get_markdown_value(row, column_index_map.get("primary_key"))
                columns.append(
                    TestDataColumn(
                        name=self._normalize_identifier(field_name),
                        sql_type=sql_type or "UNKNOWN",
                        description=description,
                        required=self._parse_required_flag(required_text),
                        default=default_value,
                        primary_key=self._parse_primary_key_flag(key_text, description),
                    )
                )

            if not columns:
                continue

            tables.append(
                TestDataTable(
                    name=table_name,
                    display_name=self._build_display_name(table_name, description_line),
                    description=description_line,
                    columns=columns,
                    source="markdown",
                )
            )

        return tables, warnings

    def _parse_create_table_columns(self, block: str) -> List[TestDataColumn]:
        columns: List[TestDataColumn] = []
        primary_keys: List[str] = []

        for item in self._split_top_level_csv(block):
            normalized = re.sub(r"\s+", " ", item).strip()
            if not normalized:
                continue

            lower_normalized = normalized.lower()
            if lower_normalized.startswith("primary key"):
                primary_keys.extend(self._extract_constraint_columns(normalized))
                continue
            if lower_normalized.startswith(("unique key", "key ", "index ", "constraint ", "unique index", "fulltext key", "spatial key")):
                continue

            column = self._parse_column_definition(normalized)
            if column:
                columns.append(column)

        primary_key_names = {name.lower() for name in primary_keys}
        for column in columns:
            if column.name.lower() in primary_key_names:
                column.primary_key = True
        return columns

    def _parse_column_definition(self, definition: str) -> Optional[TestDataColumn]:
        match = re.match(r'^[`"]?(?P<name>[A-Za-z0-9_$.]+)[`"]?\s+(?P<body>.+)$', definition)
        if not match:
            return None

        name = self._normalize_identifier(match.group("name"))
        body = re.sub(r"\s+", " ", match.group("body")).strip()
        if not body:
            return None

        type_match = re.match(
            r"^(?P<type>.+?)(?=\s+(?:NOT\s+NULL|NULL|DEFAULT|AUTO_INCREMENT|COMMENT|PRIMARY\s+KEY|UNIQUE|REFERENCES|CHECK)\b|$)",
            body,
            re.IGNORECASE,
        )
        sql_type = type_match.group("type").strip() if type_match else body
        sql_type = re.sub(r"\s+(?:CHARACTER SET|COLLATE)\s+\w+", "", sql_type, flags=re.IGNORECASE).strip()

        description = self._extract_comment(body)
        default_value = self._extract_default(body)
        required = "not null" in body.lower() and "auto_increment" not in body.lower() and not default_value
        return TestDataColumn(
            name=name,
            sql_type=sql_type or "UNKNOWN",
            description=description,
            required=required,
            default=default_value,
            primary_key=bool(re.search(r"\bprimary\s+key\b", body, re.IGNORECASE)),
            auto_increment=bool(re.search(r"\bauto_increment\b", body, re.IGNORECASE)),
        )

    def _merge_tables(self, primary_tables: List[TestDataTable], fallback_tables: List[TestDataTable]) -> List[TestDataTable]:
        merged: Dict[str, TestDataTable] = {}
        # 权威源标记：DDL 源表先于 Markdown 源表加入，DDL 字段属性具有更高可信度
        source_rank: Dict[str, str] = {}
        for table in primary_tables + fallback_tables:
            key = table.name.lower()
            existing = merged.get(key)
            if not existing:
                merged[key] = TestDataTable(
                    name=table.name,
                    display_name=table.display_name,
                    description=table.description,
                    columns=[
                        TestDataColumn(
                            name=column.name,
                            sql_type=column.sql_type,
                            description=column.description,
                            required=column.required,
                            default=column.default,
                            primary_key=column.primary_key,
                            auto_increment=column.auto_increment,
                        )
                        for column in table.columns
                    ],
                    source=table.source,
                )
                source_rank[key] = table.source
                continue

            if not existing.description and table.description:
                existing.description = table.description
            if not existing.display_name and table.display_name:
                existing.display_name = table.display_name

            # 已有源是 DDL 时，Markdown 来的约束标记仅做补充不做覆盖
            existing_is_authoritative = source_rank.get(key) == "ddl"
            existing_columns = {column.name.lower(): column for column in existing.columns}
            for column in table.columns:
                current = existing_columns.get(column.name.lower())
                if not current:
                    existing.columns.append(column)
                    existing_columns[column.name.lower()] = column
                    continue
                if not current.sql_type and column.sql_type:
                    current.sql_type = column.sql_type
                if not current.description and column.description:
                    current.description = column.description
                # DDL 源已有明确标记时不被 Markdown 源覆盖；否则取并集
                if not existing_is_authoritative:
                    current.required = current.required or column.required
                    current.primary_key = current.primary_key or column.primary_key
                elif not current.required and column.required:
                    current.required = True
                elif not current.primary_key and column.primary_key:
                    current.primary_key = True
                current.auto_increment = current.auto_increment or column.auto_increment
                if not current.default and column.default:
                    current.default = column.default

        return sorted(merged.values(), key=lambda item: item.name)

    def _build_summary(
        self,
        document_name: str,
        tables: List[TestDataTable],
        scenarios: List[TestDataScenario],
    ) -> str:
        source_name = document_name or "当前文档"
        return (
            f"已基于 {source_name} 识别 {len(tables)} 张表，"
            f"并生成 {len(scenarios)} 组 MySQL 查询、插入、更新、删除 SQL 模板。"
        )

    def _build_display_name(self, table_name: str, fallback_description: str = "") -> str:
        description = self._sanitize_description(fallback_description)
        if (
            description
            and len(description) <= 24
            and "<" not in description
            and "表名" not in description
            and "字段" not in description
            and "结构" not in description
            and not re.fullmatch(r"[A-Za-z0-9_$.]+", description)
        ):
            return description

        base_name = table_name.split(".")[-1]
        base_name = re.sub(r"^(?:xqd_|tbl_|t_|tmp_|dim_|dwd_|ods_|fact_)", "", base_name, flags=re.IGNORECASE)
        tokens = [token for token in base_name.split("_") if token]
        translated = [self.KEYWORD_LABELS[token.lower()] for token in tokens if token.lower() in self.KEYWORD_LABELS]
        if translated:
            return "".join(translated)
        return base_name or table_name

    def _build_select_sql(self, table: TestDataTable) -> str:
        column_names = [f"`{column.name}`" for column in table.columns] or ["*"]
        where_lines = self._build_where_conditions(table)
        sql_lines = [
            "SELECT",
            "  " + ",\n  ".join(column_names),
            f"FROM `{table.name}`",
        ]
        if where_lines:
            sql_lines.append("WHERE " + "\n  AND ".join(where_lines))
        sql_lines.append("LIMIT 20;")
        return "\n".join(sql_lines)

    def _build_insert_sql(self, table: TestDataTable) -> str:
        insert_columns = [column for column in table.columns if not column.auto_increment]
        if not insert_columns:
            insert_columns = table.columns[:]

        if not insert_columns:
            return f"-- 未识别到 `{table.name}` 可插入字段"

        column_lines = ",\n  ".join(f"`{column.name}`" for column in insert_columns)
        value_lines = ",\n  ".join(self._build_sample_value(column) for column in insert_columns)
        return "\n".join([
            f"INSERT INTO `{table.name}` (",
            "  " + column_lines,
            ") VALUES (",
            "  " + value_lines,
            ");",
        ])

    def _build_update_sql(self, table: TestDataTable) -> str:
        where_lines = self._build_where_conditions(table)
        if not where_lines:
            return f"-- 未生成 `{table.name}` 的 UPDATE SQL：缺少可安全定位单条记录的主键或高置信标识字段"

        update_columns = self._select_update_columns(table)
        if not update_columns:
            return f"-- 未生成 `{table.name}` 的 UPDATE SQL：未识别到可更新字段"

        assignment_lines = ",\n  ".join(
            f"`{column.name}` = {self._build_sample_value(column)}"
            for column in update_columns
        )
        return "\n".join([
            f"UPDATE `{table.name}`",
            "SET",
            "  " + assignment_lines,
            "WHERE " + "\n  AND ".join(where_lines) + ";",
        ])

    def _build_delete_sql(self, table: TestDataTable) -> str:
        where_lines = self._build_where_conditions(table)
        if not where_lines:
            return f"-- 未生成 `{table.name}` 的 DELETE SQL：缺少可安全定位单条记录的主键或高置信标识字段"

        return "\n".join([
            f"DELETE FROM `{table.name}`",
            "WHERE " + "\n  AND ".join(where_lines) + ";",
        ])

    def _build_where_conditions(self, table: TestDataTable) -> List[str]:
        return [
            f"`{column.name}` = {self._build_sample_value(column, prefer_condition=True)}"
            for column in self._select_condition_columns(table)
        ]

    def _select_condition_columns(self, table: TestDataTable) -> List[TestDataColumn]:
        primary_keys = [column for column in table.columns if column.primary_key]
        if primary_keys:
            return primary_keys[:2]

        exact_id = [column for column in table.columns if column.name.lower() == "id"]
        if exact_id:
            return exact_id[:1]

        id_like = [
            column for column in table.columns
            if column.name.lower().endswith("_id")
        ]
        if id_like:
            return id_like[:1]

        high_confidence = [
            column for column in table.columns
            if self._is_high_confidence_condition_column(column)
        ]
        if high_confidence:
            return high_confidence[:1]

        return []

    def _is_high_confidence_condition_column(self, column: TestDataColumn) -> bool:
        normalized_name = column.name.lower()
        return (
            normalized_name in {"code", "uuid", "biz_no", "order_no", "serial_no", "sn"}
            or normalized_name.endswith("_code")
            or normalized_name.endswith("_no")
            or normalized_name.endswith("_uuid")
        )

    def _select_update_columns(self, table: TestDataTable) -> List[TestDataColumn]:
        condition_names = {column.name.lower() for column in self._select_condition_columns(table)}
        candidate_columns = [
            column
            for column in table.columns
            if not column.auto_increment and column.name.lower() not in condition_names
        ]
        if not candidate_columns:
            fallback_columns = [
                column
                for column in table.columns
                if not column.auto_increment
            ]
            return fallback_columns[:1]

        # 启发式优选：包含高测试价值关键词的字段排在前面
        high_value = [
            column for column in candidate_columns
            if any(keyword in column.name.lower() for keyword in self._HIGH_VALUE_UPDATE_KEYWORDS)
        ]
        others = [
            column for column in candidate_columns
            if column not in high_value
        ]
        sorted_columns = high_value + others
        return sorted_columns[:3]

    def _build_sample_value(self, column: TestDataColumn, prefer_condition: bool = False) -> str:
        normalized_type = column.sql_type.lower()
        normalized_name = column.name.lower()
        description = column.description or column.name

        if "json" in normalized_type:
            return "JSON_OBJECT('sample_key', 'sample_value')"
        if any(token in normalized_type for token in ("datetime", "timestamp")):
            return f"'{self._now_str()}'"
        if "date" in normalized_type:
            return f"'{self._today_str()}'"
        if any(token in normalized_type for token in ("decimal", "numeric", "float", "double")):
            return "99.99"
        if "tinyint(1)" in normalized_type or normalized_name.startswith("is_") or normalized_name.startswith("has_"):
            return "1"
        if any(token in normalized_type for token in ("int", "bigint", "smallint", "mediumint")):
            if "status" in normalized_name or "state" in normalized_name:
                return "1"
            return "10001" if prefer_condition or normalized_name.endswith("_id") or normalized_name == "id" else "1"

        if any(keyword in normalized_name for keyword in ("phone", "mobile", "tel")):
            return "'13800000000'"
        if "email" in normalized_name:
            return "'qa@example.com'"
        if "url" in normalized_name:
            return "'https://example.com/sample'"
        if "status" in normalized_name or "state" in normalized_name:
            return "'INIT'"
        if "code" in normalized_name:
            return "'TEST_CODE_001'"
        if "name" in normalized_name or "title" in normalized_name:
            return "'示例名称'"
        if "remark" in normalized_name or "desc" in normalized_name or "note" in normalized_name:
            return "'示例说明'"
        return f"'示例{self._sanitize_description(description)[:12]}'"

    def _extract_constraint_columns(self, clause: str) -> List[str]:
        match = re.search(r"\(([^)]*)\)", clause)
        if not match:
            return []
        return [
            self._normalize_identifier(part)
            for part in match.group(1).split(",")
            if self._normalize_identifier(part)
        ]

    def _extract_comment(self, text: str) -> str:
        match = self.COMMENT_PATTERN.search(text or "")
        return self._sanitize_description(match.group(1) if match else "")

    def _extract_default(self, text: str) -> str:
        match = self.DEFAULT_PATTERN.search(text or "")
        if not match:
            return ""
        return match.group(1).strip().strip("'").strip('"')

    def _find_matching_parenthesis(self, text: str, opening_index: int) -> int:
        depth = 0
        quote: Optional[str] = None
        escape = False
        for index in range(opening_index, len(text)):
            char = text[index]
            if quote:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == quote:
                    quote = None
                continue

            if char in {"'", '"'}:
                quote = char
                continue
            if char == "(":
                depth += 1
                continue
            if char == ")":
                depth -= 1
                if depth == 0:
                    return index
        return -1

    def _split_top_level_csv(self, block: str) -> List[str]:
        items: List[str] = []
        current: List[str] = []
        depth = 0
        quote: Optional[str] = None
        escape = False

        for char in block:
            if quote:
                current.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == quote:
                    quote = None
                continue

            if char in {"'", '"'}:
                quote = char
                current.append(char)
                continue
            if char == "(":
                depth += 1
                current.append(char)
                continue
            if char == ")":
                depth = max(0, depth - 1)
                current.append(char)
                continue
            if char == "," and depth == 0:
                item = "".join(current).strip()
                if item:
                    items.append(item)
                current = []
                continue
            current.append(char)

        tail = "".join(current).strip()
        if tail:
            items.append(tail)
        return items

    def _split_markdown_row(self, line: str) -> List[str]:
        stripped = line.strip()
        if not stripped:
            return []
        stripped = stripped.strip("|")
        return [cell.strip() for cell in stripped.split("|")]

    def _is_markdown_separator(self, row: List[str]) -> bool:
        if not row:
            return False
        return all(bool(re.fullmatch(r":?-{3,}:?", cell.strip())) for cell in row if cell.strip())

    def _match_header_indexes(self, header: List[str]) -> Dict[str, int]:
        indexes: Dict[str, int] = {}
        for index, raw_name in enumerate(header):
            normalized = re.sub(r"\s+", " ", raw_name).strip().lower()
            for key, aliases in self.HEADER_ALIAS_MAP.items():
                if normalized in {alias.lower() for alias in aliases} and key not in indexes:
                    indexes[key] = index
        return indexes

    def _get_markdown_value(self, row: List[str], index: Optional[int]) -> str:
        if index is None or index < 0 or index >= len(row):
            return ""
        return row[index].strip()

    def _infer_table_name_from_context(self, context_lines: List[str]) -> str:
        for raw_line in reversed(context_lines):
            line = raw_line.strip().strip("#").strip()
            if not line:
                continue
            match = re.search(r"表名[:：]\s*([A-Za-z][A-Za-z0-9_$.]*)", line, re.IGNORECASE)
            if match:
                return self._normalize_identifier(match.group(1))

            backtick_match = re.search(r"`([A-Za-z][A-Za-z0-9_$.]*)`", line)
            if backtick_match:
                return self._normalize_identifier(backtick_match.group(1))

            token_match = re.search(r"\b([A-Za-z][A-Za-z0-9_]*_[A-Za-z0-9_]+)\b", line)
            if token_match:
                candidate = token_match.group(1)
                if self._is_plausible_table_name(candidate):
                    return self._normalize_identifier(candidate)

        return ""

    def _is_plausible_table_name(self, candidate: str) -> bool:
        """判断一个含下划线的 token 是否可能是表名而非字段名。"""
        normalized = candidate.lower()
        # 排除常见字段名后缀（如 created_at、user_id 等）
        for suffix in self._FIELD_NAME_SUFFIXES:
            if normalized.endswith(suffix):
                return False
        # 要求至少含 2 个下划线分段且总长度足够
        parts = [part for part in normalized.split("_") if part]
        if len(parts) < 2 or len(normalized) <= 4:
            return False
        return True

    def _parse_required_flag(self, value: str) -> bool:
        normalized = str(value or "").strip().lower()
        if not normalized:
            return False
        if normalized in {"否", "n", "no", "false", "null", "允许为空", "可为空"}:
            return False
        return normalized in {"是", "y", "yes", "true", "not null", "必填", "不可为空"}

    def _parse_primary_key_flag(self, key_text: str, description: str) -> bool:
        normalized_key = str(key_text or "").strip().lower()
        normalized_description = str(description or "").strip().lower()
        return normalized_key in {"主键", "pk", "primary", "primary key", "是", "yes", "y"} or "主键" in normalized_description

    def _normalize_identifier(self, value: str) -> str:
        normalized = str(value or "").strip().strip("`").strip('"').strip("'")
        if "." in normalized:
            normalized = normalized.split(".")[-1]
        return normalized

    @staticmethod
    def _today_str() -> str:
        """返回当天日期字符串，用于 SQL 样本值。"""
        return date.today().isoformat()

    @staticmethod
    def _now_str() -> str:
        """返回当前日期时间字符串，用于 SQL 样本值。"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _sanitize_description(self, value: str) -> str:
        text = str(value or "").strip()
        text = re.sub(r"\s+", " ", text)
        return text.replace("|", "/").replace("'", "")

    def _serialize_table(self, table: TestDataTable) -> Dict[str, Any]:
        return {
            "name": table.name,
            "display_name": table.display_name,
            "description": table.description,
            "columns": [
                {
                    "name": column.name,
                    "sql_type": column.sql_type,
                    "description": column.description,
                    "required": column.required,
                    "default": column.default,
                    "primary_key": column.primary_key,
                }
                for column in table.columns
            ],
            "select_sql": self._build_select_sql(table),
            "insert_sql": self._build_insert_sql(table),
            "update_sql": self._build_update_sql(table),
            "delete_sql": self._build_delete_sql(table),
        }

    def _serialize_scenario(self, scenario: TestDataScenario) -> Dict[str, Any]:
        return {
            "name": scenario.name,
            "tables": scenario.tables,
            "select_sql": scenario.select_sql,
            "insert_sql": scenario.insert_sql,
            "update_sql": scenario.update_sql,
            "delete_sql": scenario.delete_sql,
        }
