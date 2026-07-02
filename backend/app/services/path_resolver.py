from typing import Protocol

from app.services.metadata_scraper import Metadata


class _DirLister(Protocol):
    async def list_dir(self, path: str) -> list[str]: ...


CATEGORY_ROOTS = {
    "电影": "/电影",
    "电视剧": "/电视剧",
    "动漫": "/动漫",
    "综艺": "/综艺",
    "学习": "/学习",
    "_未分类": "/_未分类",
}


class PathResolver:
    def __init__(self, dir_lister: _DirLister):
        self._lister = dir_lister

    async def resolve(
        self,
        category: str,
        metadata: Metadata | None,
        share_root_name: str,
    ) -> str:
        root = CATEGORY_ROOTS.get(category, CATEGORY_ROOTS["_未分类"])
        if metadata is None:
            # 无元数据：用原分享文件夹名
            return f"{root}/{share_root_name}"

        # 学习类不强制年份
        if category == "学习":
            return f"{root}/{share_root_name}"

        # 电影/电视剧/动漫/综艺：尝试匹配已存在同名目录（多季合并）
        desired_name = f"{metadata.title} ({metadata.year})" if metadata.year else metadata.title
        existing = await self._lister.list_dir(root)
        # 已有同名 → 复用
        if desired_name in existing:
            return f"{root}/{desired_name}"
        # 也兼容不带年份的同名（比如老数据）
        no_year = metadata.title
        if no_year in existing:
            return f"{root}/{no_year}"
        # 新建
        return f"{root}/{desired_name}"
