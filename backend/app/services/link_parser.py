import hashlib
import re
from dataclasses import dataclass

URL_RE = re.compile(
    r"https?://(?:anyme\.)?115\.com/s/(?P<id>[A-Za-z0-9_-]+)"
    r"(?:\?[^#\s]*)?",
    re.IGNORECASE,
)
PASSWORD_RE = re.compile(r"(?:password|提取码|访问码|密码)\s*[:：]?\s*(?P<code>[A-Za-z0-9]{1,12})", re.IGNORECASE)
SHORT_RE = re.compile(r"115\.com/s/(?P<id>[A-Za-z0-9_-]+)", re.IGNORECASE)


@dataclass(frozen=True)
class ShareLink:
    share_id: str          # 规范化后的小写 id
    password: str | None
    share_hash: str        # sha256(share_id)，规范化后稳定


def _normalize_id(raw: str) -> str:
    return raw.strip().lower()


def parse(text: str) -> ShareLink | None:
    if not text:
        return None
    m = URL_RE.search(text) or SHORT_RE.search(text)
    if not m:
        return None
    share_id = _normalize_id(m.group("id"))
    pwd_match = PASSWORD_RE.search(text)
    password = pwd_match.group("code") if pwd_match else None
    # 若 URL 中有 ?password=xxx 也兼容
    if password is None:
        qm = re.search(r"[?&]password=([^&\s#]+)", text, re.IGNORECASE)
        if qm:
            password = qm.group(1)
    return ShareLink(
        share_id=share_id,
        password=password,
        share_hash=hashlib.sha256(share_id.encode("utf-8")).hexdigest(),
    )


def parse_all(text: str) -> list[ShareLink]:
    if not text:
        return []
    results: list[ShareLink] = []
    seen: set[str] = set()
    for m in re.finditer(URL_RE, text):
        share_id = _normalize_id(m.group("id"))
        if share_id in seen:
            continue
        seen.add(share_id)
        pwd_match = PASSWORD_RE.search(text)
        password = pwd_match.group("code") if pwd_match else None
        if password is None:
            qm = re.search(r"[?&]password=([^&\s#]+)", text, re.IGNORECASE)
            password = qm.group(1) if qm else None
        results.append(ShareLink(
            share_id=share_id,
            password=password,
            share_hash=hashlib.sha256(share_id.encode("utf-8")).hexdigest(),
        ))
    return results
