from pathlib import Path

from test_platform.core.services.api_suite_repository import ApiSuiteRepository


def test_api_suite_repository_versions_suite_under_same_title(tmp_path):
    repository = ApiSuiteRepository(base_dir=str(tmp_path))

    first_meta = repository.save_suite(
        spec={"title": "默认模块", "servers": [{"url": "https://example.com"}]},
        cases=[{"case_id": "platformGoods_add_success"}],
        scenes=[{"scene_id": "platformGoods_crud_flow"}],
        script="import pytest\n",
        link_plan={"ordered_case_ids": ["platformGoods_add_success"]},
    )
    second_meta = repository.save_suite(
        spec={"title": "默认模块", "servers": [{"url": "https://example.com"}]},
        cases=[{"case_id": "platformGoods_add_success"}],
        scenes=[{"scene_id": "platformGoods_crud_flow"}],
        script="import pytest\n",
        link_plan={"ordered_case_ids": ["platformGoods_add_success"]},
    )

    assert first_meta["suite_id"] == second_meta["suite_id"]
    assert first_meta["suite_version"] == 1
    assert second_meta["suite_version"] == 2
    assert Path(second_meta["storage_path"]).exists()

    loaded = repository.load_suite(second_meta["suite_id"], version=2)
    assert loaded is not None
    assert loaded["spec"]["title"] == "默认模块"
    assert loaded["link_plan"]["ordered_case_ids"] == ["platformGoods_add_success"]

    items = repository.list_suites(limit=10)
    assert items[0]["suite_id"] == second_meta["suite_id"]
    assert items[0]["latest_version"] == 2
    assert items[0]["case_count"] == 1
    assert items[0]["scene_count"] == 1
