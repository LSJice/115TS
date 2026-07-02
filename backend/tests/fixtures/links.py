SAMPLES = [
    # (raw_text, expected_url, expected_code, expected_hash_consistency)
    ("https://115.com/s/abc123?password=xyz", "abc123", "xyz", True),
    ("https://115.com/s/abc123?password=xyz", "abc123", "xyz", True),  # 与上行同 hash
    ("https://115.com/s/abc123/?password=xyz", "abc123", "xyz", True),  # 末尾斜杠 → 同 hash
    ("HTTPS://115.com/s/ABC123?password=xyz", "abc123", "xyz", True),  # 大小写 → 同 hash
    ("链接: 115.com/s/def456 提取码: pwd", "def456", "pwd", True),
    ("分享 https://115.com/s/ghi789?password=aaa 收藏一下", "ghi789", "aaa", True),
    ("https://115.com/s/zzz999", "zzz999", None, True),  # 无提取码
    ("没有链接的纯文本", None, None, False),
]

NORMALIZATION_PAIRS = [
    # 不同写法应规范化为同一 share_id → 同一 hash
    ("https://115.com/s/CaseSensitive123?password=p", "https://115.com/s/casesensitive123/?password=p"),
]
