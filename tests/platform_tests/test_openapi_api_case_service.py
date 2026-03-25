import json

from test_platform.core.services.api_case_service import ApiCaseService
from test_platform.core.services.openapi_asset_service import OpenApiAssetService


SAMPLE_OPENAPI_SPEC = json.dumps(
    {
        "openapi": "3.0.1",
        "info": {
            "title": "默认模块",
            "description": "",
            "version": "1.0.0",
        },
        "tags": [
            {
                "name": "平台带货管理",
            }
        ],
        "paths": {
            "/admin/platformGoods/adminList": {
                "post": {
                    "summary": "adminList",
                    "tags": ["平台带货管理"],
                    "parameters": [
                        {"name": "cookie", "in": "cookie", "schema": {"type": "string"}},
                        {"name": "userId", "in": "cookie", "schema": {"type": "string"}},
                        {"name": "Authorization-User", "in": "header", "schema": {"type": "string"}},
                        {"name": "Authorization", "in": "header", "schema": {"type": "string"}},
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PlatformGoodsQueryDto"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponsePageResPlatformGoodsDto"}
                                }
                            }
                        }
                    },
                }
            },
            "/admin/platformGoods/add": {
                "post": {
                    "summary": "add",
                    "tags": ["平台带货管理"],
                    "parameters": [
                        {"name": "cookie", "in": "cookie", "schema": {"type": "string"}},
                        {"name": "userId", "in": "cookie", "schema": {"type": "string"}},
                        {"name": "Authorization-User", "in": "header", "schema": {"type": "string"}},
                        {"name": "Authorization", "in": "header", "schema": {"type": "string"}},
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PlatformGoodsAddDto"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"}
                                }
                            }
                        }
                    },
                }
            },
            "/admin/platformGoods/update": {
                "post": {
                    "summary": "update",
                    "tags": ["平台带货管理"],
                    "parameters": [
                        {"name": "Authorization", "in": "header", "schema": {"type": "string"}}
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PlatformGoodsUpdateDto"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"}
                                }
                            }
                        }
                    },
                }
            },
            "/admin/platformGoods/delete": {
                "post": {
                    "summary": "delete",
                    "tags": ["平台带货管理"],
                    "parameters": [
                        {"name": "Authorization", "in": "header", "schema": {"type": "string"}}
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PlatformGoodsUpdateStatusDto"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"}
                                }
                            }
                        }
                    },
                }
            },
            "/admin/platformGoods/updateStatus": {
                "post": {
                    "summary": "updateStatus",
                    "tags": ["平台带货管理"],
                    "parameters": [
                        {"name": "Authorization", "in": "header", "schema": {"type": "string"}}
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PlatformGoodsUpdateStatusDto"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiResponse"}
                                }
                            }
                        }
                    },
                }
            },
        },
        "components": {
            "schemas": {
                "ApiResponse": {
                    "type": "object",
                    "properties": {
                        "state": {"$ref": "#/components/schemas/State"},
                        "data": {"type": "object"},
                        "id": {"type": "string"},
                        "timestamp": {"type": "integer", "format": "int64"},
                    },
                },
                "State": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "integer"},
                        "msg": {"type": "string"},
                    },
                },
                "ApiResponsePageResPlatformGoodsDto": {
                    "type": "object",
                    "properties": {
                        "state": {"$ref": "#/components/schemas/State"},
                        "data": {"$ref": "#/components/schemas/PageResPlatformGoodsDto"},
                        "id": {"type": "string"},
                        "timestamp": {"type": "integer", "format": "int64"},
                    },
                },
                "PageResPlatformGoodsDto": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer"},
                        "list": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/PlatformGoodsDto"},
                        },
                    },
                },
                "PlatformGoodsDto": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "format": "int64"},
                        "businessId": {"type": "integer", "format": "int64"},
                        "title": {"type": "string"},
                        "jumpUrl": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
                "PlatformGoodsQueryDto": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "default": 1},
                        "size": {"type": "integer", "default": 20},
                        "title": {"type": "string"},
                        "businessId": {"type": "integer", "format": "int64"},
                        "status": {"type": "string"},
                    },
                },
                "PlatformGoodsAddDto": {
                    "type": "object",
                    "properties": {
                        "businessId": {"type": "integer", "format": "int64"},
                        "businessType": {"type": "string"},
                        "title": {"type": "string"},
                        "subTitle": {"type": "string"},
                        "buttonName": {"type": "string"},
                        "jumpUrl": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
                "PlatformGoodsUpdateDto": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "format": "int64"},
                        "title": {"type": "string"},
                        "jumpUrl": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
                "PlatformGoodsUpdateStatusDto": {
                    "type": "object",
                    "properties": {
                        "ids": {"type": "array", "items": {"type": "integer"}},
                        "status": {"type": "string"},
                    },
                },
            },
            "securitySchemes": {
                "apikey-header-Authorization": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Authorization",
                }
            },
        },
        "servers": [
            {
                "url": "https://edu-admin.dev1.dachensky.com",
                "description": "测试环境dev1",
            }
        ],
        "security": [
            {
                "apikey-header-Authorization": []
            }
        ],
    },
    ensure_ascii=False,
)


def test_openapi_asset_service_builds_resource_groups_and_auth_profile():
    service = OpenApiAssetService()

    asset = service.parse_text(SAMPLE_OPENAPI_SPEC, file_name="platform-goods.json")

    assert asset["title"] == "默认模块"
    assert asset["openapi_version"] == "3.0.1"
    assert asset["servers"][0]["url"] == "https://edu-admin.dev1.dachensky.com"
    assert asset["auth_profile"]["required_headers"] == ["Authorization", "Authorization-User"]
    assert asset["auth_profile"]["required_cookies"] == ["cookie", "userId"]

    operation_map = {item["operation_id"]: item for item in asset["operations"]}
    assert operation_map["POST /admin/platformGoods/adminList"]["category"] == "list"
    assert operation_map["POST /admin/platformGoods/add"]["category"] == "create"
    assert operation_map["POST /admin/platformGoods/update"]["category"] == "update"
    assert operation_map["POST /admin/platformGoods/delete"]["category"] == "delete"
    assert operation_map["POST /admin/platformGoods/updateStatus"]["category"] == "status"

    resource = asset["resources"][0]
    assert resource["resource_key"] == "platformGoods"
    assert resource["tag"] == "平台带货管理"
    assert resource["lookup_fields"] == ["title", "businessId", "jumpUrl"]


def test_api_case_service_builds_crud_scene_with_lookup_when_create_response_has_no_id():
    asset_service = OpenApiAssetService()
    case_service = ApiCaseService()

    asset = asset_service.parse_text(SAMPLE_OPENAPI_SPEC, file_name="platform-goods.json")
    suite = case_service.build_suite(asset)

    case_map = {item["case_id"]: item for item in suite["cases"]}

    assert "platformGoods_add_success" in case_map
    assert "platformGoods_lookup_after_add" in case_map
    assert "platformGoods_update_success" in case_map
    assert "platformGoods_updateStatus_success" in case_map
    assert "platformGoods_delete_success" in case_map
    assert "platformGoods_verify_deleted" in case_map

    lookup_case = case_map["platformGoods_lookup_after_add"]
    assert lookup_case["operation_id"] == "POST /admin/platformGoods/adminList"
    assert lookup_case["depends_on"] == ["platformGoods_add_success"]
    assert lookup_case["extract"][0]["from"] == "lookup"
    assert lookup_case["extract"][0]["pick"] == "response.data.list[0].id"

    scene = suite["scenes"][0]
    assert scene["scene_id"] == "platformGoods_crud_flow"
    assert scene["steps"] == [
        "platformGoods_add_success",
        "platformGoods_lookup_after_add",
        "platformGoods_update_success",
        "platformGoods_updateStatus_success",
        "platformGoods_delete_success",
        "platformGoods_verify_deleted",
    ]
