from dataclasses import dataclass
from typing import Literal

import httpx
from loguru import logger


@dataclass(frozen=True)
class Metadata:
    tmdb_id: int
    title: str
    year: int | None
    kind: Literal["movie", "tv"]
    seasons: int | None = None


class MetadataScraper:
    BASE = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str, language: str = "zh-CN", timeout: float = 10.0):
        self.api_key = api_key
        self.language = language
        self.timeout = timeout

    async def search(
        self,
        query: str,
        category: str,
        year: int | None,
    ) -> Metadata | None:
        if not self.api_key or not query:
            return None
        if category == "电影":
            endpoint = "movie"
            year_param = "primary_release_year"
            title_field = "title"
        else:
            # 电视剧/动漫 统一走 tv
            endpoint = "tv"
            year_param = "first_air_date_year"
            title_field = "name"
        params = {
            "api_key": self.api_key,
            "language": self.language,
            "query": query,
        }
        if year:
            params[year_param] = year
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(f"{self.BASE}/search/{endpoint}", params=params)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                # 注意：不打印异常详情或 URL，因为 URL/params 中含 api_key
                logger.warning("TMDB search failed: {}", type(e).__name__)
                return None
            data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        # 年份过滤：若用户给了 year，挑匹配的；否则取第一个
        chosen = None
        if year:
            for r in results:
                d = r.get("release_date") or r.get("first_air_date") or ""
                if d.startswith(str(year)):
                    chosen = r
                    break
        if chosen is None:
            chosen = results[0]
        date_str = chosen.get("release_date") or chosen.get("first_air_date") or ""
        parsed_year = int(date_str[:4]) if len(date_str) >= 4 else None
        return Metadata(
            tmdb_id=chosen["id"],
            title=chosen.get(title_field) or chosen.get("original_title") or chosen.get("original_name") or query,
            year=parsed_year,
            kind=endpoint,  # type: ignore
            seasons=chosen.get("number_of_seasons"),
        )
