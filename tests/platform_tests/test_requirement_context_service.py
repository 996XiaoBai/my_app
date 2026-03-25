from test_platform.core.services.requirement_context_service import RequirementContextService


def test_requirement_context_service_reuses_cached_requirement():
    call_count = {"value": 0}
    requirement = (
        "用户可以使用账号密码登录系统，登录成功后进入首页并展示工作台摘要。"
        "系统需要校验账号状态、密码错误次数、锁定时长以及登录后的权限初始化。"
        "同时还需要记录登录日志、异常告警和设备信息，用于后续安全审计与问题追踪。"
    )

    def identify_modules(text, filename):
        call_count["value"] += 1
        return [{"name": "登录", "pages": [1], "description": "登录模块"}]

    service = RequirementContextService(module_identifier=identify_modules)

    first = service.prepare_context(requirement=requirement)
    second = service.prepare_context(requirement=requirement)

    assert first["context_id"] == second["context_id"]
    assert first["modules"][0]["name"] == "登录"
    assert second["cache_hit"] is True
    assert call_count["value"] == 1


def test_requirement_context_service_reads_non_pdf_file(tmp_path):
    source = tmp_path / "req.md"
    source.write_text(
        "# 登录需求\n"
        "用户输入账号密码后进入首页，并根据角色显示菜单、消息提醒和待办事项。\n"
        "系统需要校验密码错误次数、锁定规则、登录日志和异常告警。\n"
        "同时需要支持多端登录提示、设备识别和权限初始化。\n",
        encoding="utf-8"
    )

    service = RequirementContextService(
        module_identifier=lambda text, filename: [{"name": "登录", "pages": [1], "description": filename}]
    )

    result = service.prepare_context(file_path=str(source))

    assert result["context"]["combined_text"].startswith("# 登录需求")
    assert result["modules"][0]["description"] == "req.md"
    assert result["cache_hit"] is False


def test_requirement_context_service_evicts_expired_context():
    current_time = {"value": 1000.0}
    call_count = {"value": 0}

    def identify_modules(text, filename):
        call_count["value"] += 1
        return [{"name": "登录", "pages": [1], "description": filename}]

    service = RequirementContextService(
        module_identifier=identify_modules,
        cache_ttl_seconds=10,
        max_entries=4,
        now_provider=lambda: current_time["value"],
    )

    first = service.prepare_context(requirement="登录需求说明" * 20)

    current_time["value"] += 11

    assert service.get_context(first["context_id"]) is None

    second = service.prepare_context(requirement="登录需求说明" * 20)

    assert second["context_id"] != first["context_id"]
    assert second["cache_hit"] is False
    assert call_count["value"] == 2


def test_requirement_context_service_evicts_least_recently_used_context():
    current_time = {"value": 2000.0}

    service = RequirementContextService(
        module_identifier=lambda text, filename: [{"name": filename, "pages": [1], "description": text[:4]}],
        cache_ttl_seconds=300,
        max_entries=2,
        now_provider=lambda: current_time["value"],
    )

    first = service.prepare_context(requirement="第一个需求说明" * 20)
    current_time["value"] += 1
    second = service.prepare_context(requirement="第二个需求说明" * 20)
    current_time["value"] += 1

    cached_first = service.get_context(first["context_id"])
    assert cached_first is not None
    assert cached_first["cache_hit"] is True

    current_time["value"] += 1
    third = service.prepare_context(requirement="第三个需求说明" * 20)

    assert service.get_context(second["context_id"]) is None
    assert service.get_context(first["context_id"]) is not None
    assert service.get_context(third["context_id"]) is not None


def test_requirement_context_service_uses_pdf_context_builder_and_reuses_cache(tmp_path):
    source = tmp_path / "req.pdf"
    source.write_bytes(b"%PDF-1.4 fake payload for cache testing")
    builder_calls = {"value": 0}

    def identify_modules(text, filename):
        return [{"name": "登录", "pages": [1], "description": filename}]

    def build_pdf_context(file_path: str, max_pages: int):
        builder_calls["value"] += 1
        assert file_path.endswith("req.pdf")
        assert max_pages == 2
        return (
            "第 1 页 登录需求说明，包含账号密码校验、错误次数限制、锁定规则、登录日志、权限初始化与设备识别。\n\n"
            "第 2 页 风险说明，包含异常告警、多端登录提示、角色菜单渲染和审计追踪要求。",
            {
                1: "第 1 页 登录需求说明，包含账号密码校验、错误次数限制、锁定规则、登录日志、权限初始化与设备识别。",
                2: "第 2 页 风险说明，包含异常告警、多端登录提示、角色菜单渲染和审计追踪要求。",
            },
        )

    service = RequirementContextService(
        module_identifier=identify_modules,
        pdf_context_builder=build_pdf_context,
    )

    first = service.prepare_context(file_path=str(source), max_pages=2)
    second = service.prepare_context(file_path=str(source), max_pages=2)

    assert first["context"]["combined_text"].startswith("第 1 页")
    assert first["modules"][0]["description"] == "req.pdf"
    assert second["cache_hit"] is True
    assert builder_calls["value"] == 1


def test_requirement_context_service_preserves_pdf_vision_context(tmp_path):
    source = tmp_path / "prototype.pdf"
    source.write_bytes(b"%PDF-1.4 fake payload for vision context")

    def build_pdf_context(file_path: str, max_pages: int):
        assert file_path.endswith("prototype.pdf")
        assert max_pages == 3
        return {
            "combined_text": "第 1 页 原型说明\n\n第 2 页 交互流程",
            "page_texts": {
                1: "第 1 页 原型说明",
                2: "第 2 页 交互流程",
            },
            "vision_files_map": {
                2: {
                    "type": "image",
                    "upload_file_id": "file-2",
                }
            },
            "pages": [
                {"page_num": 1, "text": "第 1 页 原型说明"},
                {"page_num": 2, "text": "第 2 页 交互流程"},
            ],
        }

    service = RequirementContextService(
        module_identifier=lambda text, filename: [{"name": "原型", "pages": [1, 2], "description": filename}],
        pdf_context_builder=build_pdf_context,
    )

    result = service.prepare_context(file_path=str(source), max_pages=3)

    assert result["context"]["combined_text"].startswith("第 1 页")
    assert result["context"]["vision_files_map"][2]["upload_file_id"] == "file-2"
    assert len(result["context"]["pages"]) == 2
    assert result["context"]["page_texts"][2] == "第 2 页 交互流程"
