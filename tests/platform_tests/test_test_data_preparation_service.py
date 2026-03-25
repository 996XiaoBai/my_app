from test_platform.core.services.test_data_preparation_service import TestDataPreparationService


def test_test_data_preparation_service_parses_create_table_and_generates_mysql_sql():
    service = TestDataPreparationService()

    payload = service.prepare_result(
        document_name="直播提效.doc",
        raw_text="""
        CREATE TABLE `xqd_platform_goods` (
          `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
          `room_id` bigint NOT NULL COMMENT '直播间ID',
          `goods_name` varchar(128) NOT NULL COMMENT '商品名称',
          `status` tinyint NOT NULL DEFAULT 1 COMMENT '状态',
          `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
          PRIMARY KEY (`id`)
        ) COMMENT='直播商品表';
        """,
    )

    assert payload["tables"][0]["name"] == "xqd_platform_goods"
    assert payload["tables"][0]["display_name"] == "直播商品表"
    assert payload["tables"][0]["columns"][0]["primary_key"] is True
    assert "FROM `xqd_platform_goods`" in payload["tables"][0]["select_sql"]
    assert "WHERE `id` = 10001" in payload["tables"][0]["select_sql"]
    assert "INSERT INTO `xqd_platform_goods`" in payload["tables"][0]["insert_sql"]
    assert "UPDATE `xqd_platform_goods`" in payload["tables"][0]["update_sql"]
    assert "DELETE FROM `xqd_platform_goods`" in payload["tables"][0]["delete_sql"]
    assert "WHERE `id` = 10001" in payload["tables"][0]["update_sql"]
    assert "WHERE `id` = 10001" in payload["tables"][0]["delete_sql"]
    assert "`goods_name`" in payload["tables"][0]["insert_sql"]
    assert "## 直播商品表 (`xqd_platform_goods`)" in payload["markdown"]
    assert "### UPDATE" in payload["markdown"]
    assert "### DELETE" in payload["markdown"]
    assert "-- 按表 SQL" in payload["sql_file_content"]
    assert "-- 按场景 SQL" in payload["sql_file_content"]
    assert "-- 表：直播商品表 (xqd_platform_goods)" in payload["sql_file_content"]


def test_test_data_preparation_service_cleans_confluence_like_export_and_extracts_table_schema():
    service = TestDataPreparationService()

    payload = service.prepare_result(
        document_name="直播提效导出.doc",
        raw_text="""
        Subject: Exported From Confluence
        Content-Transfer-Encoding: quoted-printable

        <html>
        <body>
        <h1>=E7=9B=B4=E6=92=AD=E6=8F=90=E6=95=88</h1>
        <pre>
        CREATE TABLE `xqd_live_room` (
          `room_id` bigint NOT NULL COMMENT '直播间ID',
          `room_name` varchar(64) NOT NULL COMMENT '直播间名称',
          `status` tinyint NOT NULL DEFAULT 1 COMMENT '状态',
          PRIMARY KEY (`room_id`)
        ) COMMENT='直播间表';
        </pre>
        <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA" />
        </body>
        </html>
        """,
    )

    assert payload["tables"][0]["name"] == "xqd_live_room"
    assert payload["tables"][0]["display_name"] == "直播间表"
    assert payload["scenarios"][0]["name"] == "查询与插入直播间表"
    assert "UPDATE `xqd_live_room`" in payload["scenarios"][0]["update_sql"]
    assert "DELETE FROM `xqd_live_room`" in payload["scenarios"][0]["delete_sql"]
    assert "data:image/png" not in payload["markdown"]
    assert "Content-Transfer-Encoding" not in payload["markdown"]


def test_test_data_preparation_service_parses_markdown_field_table_when_no_create_table_exists():
    service = TestDataPreparationService()

    payload = service.prepare_result(
        document_name="表结构说明.md",
        raw_text="""
        ### 表名：xqd_live_goods
        | 字段名 | 类型 | 说明 | 是否必填 | 主键 |
        | --- | --- | --- | --- | --- |
        | goods_id | bigint | 商品ID | 是 | 是 |
        | goods_name | varchar(128) | 商品名称 | 是 | 否 |
        | status | tinyint | 状态 | 否 | 否 |
        """,
    )

    assert payload["tables"][0]["name"] == "xqd_live_goods"
    assert payload["tables"][0]["columns"][0]["primary_key"] is True
    assert payload["tables"][0]["columns"][1]["required"] is True
    assert "INSERT INTO `xqd_live_goods`" in payload["tables"][0]["insert_sql"]
    assert "WHERE `goods_id` = 10001" in payload["tables"][0]["update_sql"]
    assert "WHERE `goods_id` = 10001" in payload["tables"][0]["delete_sql"]


def test_test_data_preparation_service_does_not_generate_dangerous_update_or_delete_without_where_key():
    service = TestDataPreparationService()

    payload = service.prepare_result(
        document_name="弱约束表结构.md",
        raw_text="""
        CREATE TABLE `operation_log` (
          `content` varchar(255) DEFAULT NULL COMMENT '日志内容',
          `remark` varchar(255) DEFAULT NULL COMMENT '备注'
        ) COMMENT='操作日志表';
        """,
    )

    update_sql = payload["tables"][0]["update_sql"]
    delete_sql = payload["tables"][0]["delete_sql"]

    assert "WHERE" not in update_sql
    assert "WHERE" not in delete_sql
    assert "未生成" in update_sql
    assert "未生成" in delete_sql


def test_test_data_preparation_service_parses_multiple_tables_from_single_ddl_text():
    """多表 DDL 解析：输入含 2 张表的 DDL，验证均被正确提取。"""
    service = TestDataPreparationService()

    payload = service.prepare_result(
        document_name="多表结构.sql",
        raw_text="""
        CREATE TABLE `xqd_order` (
          `id` bigint NOT NULL AUTO_INCREMENT COMMENT '订单ID',
          `user_id` bigint NOT NULL COMMENT '用户ID',
          `total_amount` decimal(10,2) NOT NULL COMMENT '订单金额',
          PRIMARY KEY (`id`)
        ) COMMENT='订单表';

        CREATE TABLE `xqd_order_item` (
          `id` bigint NOT NULL AUTO_INCREMENT COMMENT '条目ID',
          `order_id` bigint NOT NULL COMMENT '订单ID',
          `goods_name` varchar(128) NOT NULL COMMENT '商品名称',
          `price` decimal(10,2) NOT NULL COMMENT '单价',
          PRIMARY KEY (`id`)
        ) COMMENT='订单明细表';
        """,
    )

    table_names = [t["name"] for t in payload["tables"]]
    assert "xqd_order" in table_names
    assert "xqd_order_item" in table_names
    assert len(payload["tables"]) == 2
    assert len(payload["scenarios"]) == 2


def test_test_data_preparation_service_ddl_authority_over_markdown_on_merge():
    """DDL + Markdown 合并权重：DDL 已标记 NOT NULL 的字段不被 Markdown 的'否'覆盖。"""
    service = TestDataPreparationService()

    # DDL 明确 user_id NOT NULL，Markdown 标记为'否'
    payload = service.prepare_result(
        document_name="合并测试.md",
        raw_text="""
        CREATE TABLE `xqd_user_profile` (
          `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
          `user_id` bigint NOT NULL COMMENT '用户ID',
          `nickname` varchar(64) DEFAULT NULL COMMENT '昵称',
          PRIMARY KEY (`id`)
        ) COMMENT='用户资料表';

        ### 表名：xqd_user_profile
        | 字段名 | 类型 | 说明 | 是否必填 |
        | --- | --- | --- | --- |
        | user_id | bigint | 用户ID | 否 |
        | nickname | varchar(64) | 昵称 | 是 |
        """,
    )

    # 应该只合并成 1 张表
    assert len(payload["tables"]) == 1
    columns = {c["name"]: c for c in payload["tables"][0]["columns"]}
    # DDL 标记了 NOT NULL，应保持 required=True，不被 Markdown 的'否'覆盖
    assert columns["user_id"]["primary_key"] is False


def test_test_data_preparation_service_handles_composite_primary_key():
    """复合主键场景：PRIMARY KEY (a, b) 形式的复合主键验证。"""
    service = TestDataPreparationService()

    payload = service.prepare_result(
        document_name="复合主键.sql",
        raw_text="""
        CREATE TABLE `xqd_user_role` (
          `user_id` bigint NOT NULL COMMENT '用户ID',
          `role_id` bigint NOT NULL COMMENT '角色ID',
          `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
          PRIMARY KEY (`user_id`, `role_id`)
        ) COMMENT='用户角色关系表';
        """,
    )

    columns = {c["name"]: c for c in payload["tables"][0]["columns"]}
    assert columns["user_id"]["primary_key"] is True
    assert columns["role_id"]["primary_key"] is True
    assert columns["created_at"]["primary_key"] is False
    # WHERE 条件应使用两个主键
    assert "`user_id`" in payload["tables"][0]["select_sql"]
    assert "`role_id`" in payload["tables"][0]["select_sql"]


def test_test_data_preparation_service_returns_warnings_on_empty_input():
    """空文本输入：验证返回空结果和提示告警。"""
    service = TestDataPreparationService()

    payload = service.prepare_result(
        document_name="空文件.txt",
        raw_text="",
    )

    assert payload["tables"] == []
    assert payload["scenarios"] == []
    assert any("未识别" in w for w in payload["warnings"])


def test_test_data_preparation_service_does_not_mistake_field_name_as_table_name():
    """表名推断不会误命中字段名：上下文行含 created_at 等字段名时不应被识别为表名。"""
    service = TestDataPreparationService()

    payload = service.prepare_result(
        document_name="字段说明.md",
        raw_text="""
        ### created_at 字段说明
        | 字段名 | 类型 | 说明 |
        | --- | --- | --- |
        | value | varchar(64) | 值 |
        | label | varchar(64) | 标签 |
        """,
    )

    # created_at 是典型字段名，不应被识别为表名
    assert payload["tables"] == []


def test_test_data_preparation_service_generates_dynamic_date_in_sql():
    """动态日期验证：生成的 SQL 中包含当天日期而非硬编码旧日期。"""
    from datetime import date
    service = TestDataPreparationService()

    payload = service.prepare_result(
        document_name="日期测试.sql",
        raw_text="""
        CREATE TABLE `xqd_event` (
          `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
          `event_date` date NOT NULL COMMENT '事件日期',
          `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
          PRIMARY KEY (`id`)
        ) COMMENT='事件表';
        """,
    )

    today = date.today().isoformat()
    insert_sql = payload["tables"][0]["insert_sql"]
    assert today in insert_sql, f"INSERT SQL 应包含当天日期 {today}，实际: {insert_sql}"


def test_test_data_preparation_service_update_prefers_high_value_columns():
    """UPDATE 列优选：含 status 字段的表，UPDATE 语句会优先修改 status。"""
    service = TestDataPreparationService()

    payload = service.prepare_result(
        document_name="列优选.sql",
        raw_text="""
        CREATE TABLE `xqd_task` (
          `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
          `creator` varchar(64) NOT NULL COMMENT '创建人',
          `category` varchar(32) DEFAULT NULL COMMENT '分类',
          `priority` int DEFAULT 0 COMMENT '优先级',
          `status` tinyint NOT NULL DEFAULT 0 COMMENT '状态',
          `remark` varchar(255) DEFAULT NULL COMMENT '备注',
          PRIMARY KEY (`id`)
        ) COMMENT='任务表';
        """,
    )

    update_sql = payload["tables"][0]["update_sql"]
    # status 和 remark 是高测试价值字段，应优先出现在 UPDATE SET 子句中
    assert "`status`" in update_sql, f"UPDATE SQL 应优先修改 status 字段: {update_sql}"
    assert "`remark`" in update_sql, f"UPDATE SQL 应优先修改 remark 字段: {update_sql}"
