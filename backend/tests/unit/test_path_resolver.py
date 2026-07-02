import pytest
from unittest.mock import MagicMock

from app.services.metadata_scraper import Metadata


def make_fetcher(existing_dirs: dict[str, list[str]]):
    """existing_dirs: {parent_path: [child_dir_names]}"""
    fetcher = MagicMock()
    async def list_dir(path: str) -> list[str]:
        return existing_dirs.get(path, [])
    fetcher.list_dir = list_dir
    return fetcher


@pytest.mark.asyncio
async def test_resolve_tv_with_metadata_creates_path_with_year():
    from app.services.path_resolver import PathResolver

    resolver = PathResolver(make_fetcher({"/电视剧": []}))
    md = Metadata(tmdb_id=1399, title="权力的游戏", year=2011, kind="tv", seasons=8)
    path = await resolver.resolve(category="电视剧", metadata=md, share_root_name="某分享文件夹")
    assert path == "/电视剧/权力的游戏 (2011)"


@pytest.mark.asyncio
async def test_resolve_tv_existing_dir_reused_for_multi_season():
    """已有同名目录（不带年份也复用），用于多季合并"""
    from app.services.path_resolver import PathResolver

    fetcher = make_fetcher({"/电视剧": ["权力的游戏 (2011)", "其他剧"]})
    resolver = PathResolver(fetcher)
    md = Metadata(tmdb_id=1399, title="权力的游戏", year=2011, kind="tv")
    path = await resolver.resolve("电视剧", md, "新分享")
    assert path == "/电视剧/权力的游戏 (2011)"


@pytest.mark.asyncio
async def test_resolve_movie_no_metadata_uses_share_root():
    from app.services.path_resolver import PathResolver

    resolver = PathResolver(make_fetcher({"/电影": []}))
    path = await resolver.resolve("电影", metadata=None, share_root_name="阿凡达.2009.4K")
    assert path == "/电影/阿凡达.2009.4K"


@pytest.mark.asyncio
async def test_resolve_uncategorized():
    from app.services.path_resolver import PathResolver

    resolver = PathResolver(make_fetcher({"/_未分类": []}))
    path = await resolver.resolve("_未分类", metadata=None, share_root_name="原分享")
    assert path == "/_未分类/原分享"


@pytest.mark.asyncio
async def test_resolve_learning_skips_year_suffix():
    from app.services.path_resolver import PathResolver

    resolver = PathResolver(make_fetcher({"/学习": []}))
    path = await resolver.resolve("学习", metadata=None, share_root_name="Python进阶")
    assert path == "/学习/Python进阶"


@pytest.mark.asyncio
async def test_resolve_movie_with_metadata_includes_year():
    from app.services.path_resolver import PathResolver

    fetcher = make_fetcher({"/电影": []})
    resolver = PathResolver(fetcher)
    md = Metadata(tmdb_id=19995, title="Avatar", year=2009, kind="movie")
    path = await resolver.resolve("电影", md, "avatar.mkv")
    assert path == "/电影/Avatar (2009)"


@pytest.mark.asyncio
async def test_resolve_learning_with_metadata_ignores_year():
    """学习类即使有 metadata 也跳过年份，用 share_root_name。"""
    from app.services.path_resolver import PathResolver

    resolver = PathResolver(make_fetcher({"/学习": []}))
    md = Metadata(tmdb_id=1, title="Python进阶", year=2023, kind="tv")
    path = await resolver.resolve("学习", md, "Python进阶")
    assert path == "/学习/Python进阶"


@pytest.mark.asyncio
async def test_resolve_tv_metadata_without_year_uses_title_only():
    """metadata.year 为 None 时，仅用 title（刮削失败的边界）。"""
    from app.services.path_resolver import PathResolver

    resolver = PathResolver(make_fetcher({"/电视剧": []}))
    md = Metadata(tmdb_id=1399, title="某剧", year=None, kind="tv")
    path = await resolver.resolve("电视剧", md, "某分享")
    assert path == "/电视剧/某剧"


@pytest.mark.asyncio
async def test_resolve_tv_no_metadata_falls_back_to_share_root():
    """电视剧分类但无 metadata（刮削失败回退）的关键路径。"""
    from app.services.path_resolver import PathResolver

    resolver = PathResolver(make_fetcher({"/电视剧": []}))
    path = await resolver.resolve("电视剧", metadata=None, share_root_name="未知剧")
    assert path == "/电视剧/未知剧"
