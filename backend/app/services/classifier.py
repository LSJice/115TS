import re
from typing import Iterable

# 优先级从高到低；先命中的优先
RULES: list[tuple[str, re.Pattern]] = [
    # 学习类优先（防止 mp4 教程被误判为电影/剧）
    ("学习", re.compile(
        r"(教程|课程|讲义|lec\d+|lecture|coursera|udemy|TTC|\.pdf$|\.pptx?$|\.docx?$)",
        re.IGNORECASE,
    )),
    # 动漫：常见番剧关键词 + 日文假名片段
    ("动漫", re.compile(
        r"(动漫|番剧|国创|二次元|鬼灭|进击的巨人|海贼王|火影|死神|咒术|蜘蛛|紫罗兰|"
        r"[ぁ-ヿ]+|[一-龥]{2,8}\.(?:第\w+季|合集))",
        re.IGNORECASE,
    )),
    # 电视剧：S01E01 / 第N集 / EP\d
    ("电视剧", re.compile(
        r"(S\d{1,2}E\d{1,3}|EP\d{1,3}|第\d{1,3}集|Season\s?\d{1,2}|E\d{2,3}\.)",
        re.IGNORECASE,
    )),
    # 综艺
    ("综艺", re.compile(
        r"(综艺|真人秀|选秀|向往的生活|奔跑吧|中国好声音|歌手|快乐大本营)",
        re.IGNORECASE,
    )),
    # 电影：含 4 位年份
    ("电影", re.compile(r"(19[5-9]\d|20[0-4]\d)")),
]


def classify(file_list: Iterable[str]) -> str:
    text = "\n".join(file_list)
    for category, pattern in RULES:
        if pattern.search(text):
            return category
    return "_未分类"
