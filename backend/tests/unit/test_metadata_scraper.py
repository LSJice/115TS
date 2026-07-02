import pytest
import respx
from httpx import Response

from tests.fixtures.tmdb_responses import GOT_SEARCH, AVATAR_SEARCH, EMPTY_SEARCH


@pytest.mark.asyncio
@respx.mock
async def test_search_tv_returns_best_match():
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=Response(200, json=GOT_SEARCH)
    )
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="fake")
    result = await scraper.search(query="权力的游戏", category="电视剧", year=None)
    assert result is not None
    assert result.title == "Game of Thrones"
    assert result.year == 2011
    assert result.tmdb_id == 1399  # 修正：mock 数据中 GOT 的 id
    assert result.kind == "tv"
    assert result.seasons == 8


@pytest.mark.asyncio
@respx.mock
async def test_search_movie():
    respx.get("https://api.themoviedb.org/3/search/movie").mock(
        return_value=Response(200, json=AVATAR_SEARCH)
    )
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="fake")
    result = await scraper.search(query="Avatar", category="电影", year=2009)
    assert result is not None
    assert result.title == "Avatar"
    assert result.year == 2009
    assert result.kind == "movie"


@pytest.mark.asyncio
@respx.mock
async def test_zero_results_returns_none():
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=Response(200, json=EMPTY_SEARCH)
    )
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="fake")
    result = await scraper.search(query="不存在的剧", category="电视剧", year=None)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_no_api_key_returns_none():
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="")
    result = await scraper.search(query="anything", category="电影", year=None)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_year_filter_picks_correct_match():
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=Response(200, json=GOT_SEARCH)
    )
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="fake")
    result = await scraper.search(query="Game of Thrones", category="电视剧", year=2018)
    # year=2018 应匹配第二个（动画版 2018）
    assert result is not None
    assert result.tmdb_id == 99999


@pytest.mark.asyncio
@respx.mock
async def test_http_error_returns_none():
    """HTTP 5xx 错误应返回 None。"""
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=Response(500)
    )
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="fake")
    result = await scraper.search(query="x", category="电视剧", year=None)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_network_error_returns_none():
    """网络层错误（DNS/连接失败）应返回 None。"""
    import httpx as httpx_mod
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        side_effect=httpx_mod.ConnectError("dns fail")
    )
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="fake")
    result = await scraper.search(query="x", category="电视剧", year=None)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_anime_category_uses_tv_endpoint():
    """动漫分类应走 tv endpoint。"""
    respx.get("https://api.themoviedb.org/3/search/tv").mock(
        return_value=Response(200, json=GOT_SEARCH)
    )
    from app.services.metadata_scraper import MetadataScraper

    scraper = MetadataScraper(api_key="fake")
    result = await scraper.search(query="鬼灭之刃", category="动漫", year=None)
    assert result is not None
    assert result.kind == "tv"
