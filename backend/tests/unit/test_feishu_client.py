import pytest
import httpx
import respx

from app.adapters.feishu_client import FeishuClient, FeishuRow, _to_text


def test_to_text_none():
    assert _to_text(None) == ""


def test_to_text_str():
    assert _to_text("hello") == "hello"


def test_to_text_list_of_dicts():
    """飞书富文本字段：[{text: "abc"}, {text: "def"}] → "abcdef"。"""
    assert _to_text([{"text": "abc"}, {"text": "def"}]) == "abcdef"


def test_to_text_mixed_list():
    assert _to_text([{"text": "abc"}, "xyz"]) == "abcxyz"


def test_to_text_other_type_falls_back_to_str():
    assert _to_text(123) == "123"


@respx.mock
@pytest.mark.asyncio
async def test_get_tenant_token_cached():
    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=httpx.Response(200, json={"tenant_access_token": "token-1"})
    )
    c = FeishuClient("id", "secret", "app_tok", "tbl")
    t1 = await c._ensure_token()
    t2 = await c._ensure_token()
    assert t1 == t2 == "token-1"
    # 第二次不应再请求
    assert respx.calls.call_count == 1


@respx.mock
@pytest.mark.asyncio
async def test_list_records_single_page():
    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=httpx.Response(200, json={"tenant_access_token": "tok"})
    )
    respx.get("https://open.feishu.cn/open-apis/bitable/v1/apps/app_tok/tables/tbl/records").mock(
        return_value=httpx.Response(200, json={
            "data": {
                "has_more": False,
                "items": [
                    {"record_id": "r1", "fields": {"链接": "https://115.com/s/a", "提取码": "x"}},
                    {"record_id": "r2", "fields": {"链接": [{"text": "https://115.com/s/b"}]}},
                ],
            },
        })
    )
    c = FeishuClient("id", "secret", "app_tok", "tbl")
    rows = await c.list_records()
    assert len(rows) == 2
    assert rows[0] == FeishuRow(record_id="r1", link="https://115.com/s/a", code="x")
    assert rows[1].link == "https://115.com/s/b"
    assert rows[1].record_id == "r2"


@respx.mock
@pytest.mark.asyncio
async def test_list_records_pagination():
    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=httpx.Response(200, json={"tenant_access_token": "tok"})
    )
    # respx 按 params 区分 route 的能力受限（先注册优先级高），改用 side_effect 顺序返回。
    records_route = respx.get(
        "https://open.feishu.cn/open-apis/bitable/v1/apps/app_tok/tables/tbl/records"
    ).mock(side_effect=[
        httpx.Response(200, json={
            "data": {"has_more": True, "page_token": "pt2", "items": [
                {"record_id": "r1", "fields": {"链接": "https://115.com/s/a"}},
            ]},
        }),
        httpx.Response(200, json={
            "data": {"has_more": False, "items": [
                {"record_id": "r2", "fields": {"链接": "https://115.com/s/b"}},
            ]},
        }),
    ])
    c = FeishuClient("id", "secret", "app_tok", "tbl")
    rows = await c.list_records()
    assert len(rows) == 2
    assert rows[0].record_id == "r1"
    assert rows[1].record_id == "r2"
    assert records_route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_list_records_401_triggers_token_refresh_and_retry():
    """首次 401 → 清缓存重新拿 token → 重试一次成功（spec §7.1 错误矩阵）。"""
    token_route = respx.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    ).mock(side_effect=[
        httpx.Response(200, json={"tenant_access_token": "old"}),
        httpx.Response(200, json={"tenant_access_token": "new"}),
    ])
    records_route = respx.get(
        "https://open.feishu.cn/open-apis/bitable/v1/apps/app_tok/tables/tbl/records"
    ).mock(side_effect=[
        httpx.Response(401, json={"msg": "token expired"}),
        httpx.Response(200, json={"data": {"has_more": False, "items": []}}),
    ])
    c = FeishuClient("id", "secret", "app_tok", "tbl")
    rows = await c.list_records()
    assert rows == []
    assert token_route.call_count == 2  # 首次 + 刷新
    assert records_route.call_count == 2  # 401 + 重试


@respx.mock
@pytest.mark.asyncio
async def test_list_records_500_raises():
    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=httpx.Response(200, json={"tenant_access_token": "tok"})
    )
    respx.get("https://open.feishu.cn/open-apis/bitable/v1/apps/app_tok/tables/tbl/records").mock(
        return_value=httpx.Response(500, text="internal error")
    )
    c = FeishuClient("id", "secret", "app_tok", "tbl")
    with pytest.raises(httpx.HTTPStatusError):
        await c.list_records()


@respx.mock
@pytest.mark.asyncio
async def test_custom_column_names_respected():
    """用户可在配置中改列名；client 必须按列名取值。"""
    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=httpx.Response(200, json={"tenant_access_token": "tok"})
    )
    respx.get("https://open.feishu.cn/open-apis/bitable/v1/apps/app_tok/tables/tbl/records").mock(
        return_value=httpx.Response(200, json={
            "data": {"has_more": False, "items": [
                {"record_id": "r1", "fields": {"url": "https://115.com/s/a", "pwd": "x"}},
            ]},
        })
    )
    c = FeishuClient(
        "id", "secret", "app_tok", "tbl",
        link_column="url", code_column="pwd", remark_column="note",
    )
    rows = await c.list_records()
    assert rows[0].link == "https://115.com/s/a"
    assert rows[0].code == "x"
