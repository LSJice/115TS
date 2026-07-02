"""p115client share_snap 响应的 mock 夹具。

字段参照 share_snap 文档：
- data.file_name: 分享根目录/根文件名
- data.is_dir: 是否目录
- data.file_list: 分享内文件列表，每项含 file_name/file_category/size
- state: 115 风格的成功标志
"""

SHARE_CONTENT_GOT = {
    "data": {
        "file_name": "Game.of.Thrones.Complete",
        "file_category": "0",
        "size": "12345",
        "is_dir": True,
        "file_list": [
            {"file_name": "Game.of.Thrones.S01E01.mkv", "file_category": "video", "size": 1024 ** 4},
            {"file_name": "Game.of.Thrones.S01E02.mkv", "file_category": "video", "size": 1024 ** 4},
        ],
    },
    "state": True,
}

SHARE_CONTENT_FLAT = {
    "data": {
        "file_name": "movie-collection",
        "is_dir": True,
        "file_list": [
            {"file_name": "Avatar.2009.2160p.mkv", "file_category": "video", "size": 1024 ** 4 * 50},
        ],
    },
    "state": True,
}
