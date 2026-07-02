from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.login_manager import LoginManager

router = APIRouter(prefix="/api/dirs", tags=["dirs"])

ROOTS = ["电影", "电视剧", "动漫", "综艺", "学习"]


class DirNode(BaseModel):
    name: str
    cid: int
    is_dir: bool = True
    children: list["DirNode"] = []


@router.get("/roots")
async def get_roots():
    """返回五大类目录的 cid（需要登录后调用）"""
    from app.api.auth import get_login_manager
    lm = get_login_manager()
    if not lm.is_logged_in():
        raise HTTPException(401, "未登录")
    client = lm.get_client()
    result = []
    for name in ROOTS:
        try:
            # 在 115 根目录下找名为 name 的子目录
            resp = client.cd_and_path_name_to_cid(path="/", name=name)
            cid = resp.get("data", {}).get("cid", 0) if isinstance(resp, dict) else 0
        except Exception:
            cid = 0
        result.append({"name": name, "cid": cid})
    return {"roots": result}


@router.get("/browse")
async def browse(cid: int = 0):
    from app.api.auth import get_login_manager
    lm = get_login_manager()
    if not lm.is_logged_in():
        raise HTTPException(401, "未登录")
    client = lm.get_client()
    try:
        resp = client.dir_files(cid=cid)
    except Exception as e:
        raise HTTPException(500, str(e))
    files = resp.get("data", []) if isinstance(resp, dict) else []
    return {
        "items": [
            {"name": f.get("name", ""), "cid": f.get("cid", 0), "is_dir": f.get("type") == "0"}
            for f in files
        ]
    }
