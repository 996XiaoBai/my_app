from test_platform.core.services.api_linking_service import ApiLinkingService


def test_api_linking_service_reorders_scene_steps_and_indexes_dependencies():
    service = ApiLinkingService()

    plan = service.build_link_plan(
        cases=[
            {
                "case_id": "platformGoods_update_success",
                "depends_on": ["platformGoods_add_success"],
                "extract": [],
            },
            {
                "case_id": "platformGoods_add_success",
                "depends_on": [],
                "extract": [{"name": "resource_id", "from": "response", "pick": "response.data.id"}],
            },
            {
                "case_id": "platformGoods_verify_deleted",
                "depends_on": ["platformGoods_update_success"],
                "extract": [],
            },
            {
                "case_id": "health_check_success",
                "depends_on": [],
                "extract": [],
            },
        ],
        scenes=[
            {
                "scene_id": "platformGoods_crud_flow",
                "steps": [
                    "platformGoods_verify_deleted",
                    "platformGoods_update_success",
                    "platformGoods_add_success",
                ],
            }
        ],
    )

    assert plan["ordered_case_ids"] == [
        "platformGoods_add_success",
        "platformGoods_update_success",
        "platformGoods_verify_deleted",
        "health_check_success",
    ]
    assert plan["standalone_case_ids"] == ["health_check_success"]
    assert plan["case_dependencies"]["platformGoods_update_success"] == ["platformGoods_add_success"]
    assert plan["scene_orders"][0]["scene_id"] == "platformGoods_crud_flow"
    assert plan["scene_orders"][0]["ordered_steps"] == [
        "platformGoods_add_success",
        "platformGoods_update_success",
        "platformGoods_verify_deleted",
    ]
    assert plan["extract_variables"]["resource_id"] == ["platformGoods_add_success"]


def test_api_linking_service_warns_for_missing_dependency_and_duplicate_extract_variable():
    service = ApiLinkingService()

    plan = service.build_link_plan(
        cases=[
            {
                "case_id": "platformGoods_add_success",
                "depends_on": [],
                "extract": [{"name": "resource_id", "pick": "response.data.id"}],
            },
            {
                "case_id": "platformGoods_lookup_after_add",
                "depends_on": ["platformGoods_add_success", "missing_case"],
                "extract": [{"name": "resource_id", "pick": "response.data.list[0].id"}],
            },
        ],
        scenes=[],
    )

    warning_text = "\n".join(plan["warnings"])
    assert "missing_case" in warning_text
    assert "resource_id" in warning_text
