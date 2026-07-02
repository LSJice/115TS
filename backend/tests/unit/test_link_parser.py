import pytest
from tests.fixtures.links import SAMPLES, NORMALIZATION_PAIRS


def test_parse_each_sample():
    from app.services.link_parser import parse
    for raw, expected_id, expected_code, _ in SAMPLES:
        result = parse(raw)
        if expected_id is None:
            assert result is None, f"应解析失败: {raw}"
        else:
            assert result is not None, f"应解析成功: {raw}"
            assert result.share_id == expected_id
            assert result.password == expected_code


def test_hash_consistency_for_normalization():
    from app.services.link_parser import parse
    for a, b in NORMALIZATION_PAIRS:
        ra, rb = parse(a), parse(b)
        assert ra is not None and rb is not None
        assert ra.share_hash == rb.share_hash, f"规范化失败：{a} vs {b}"


def test_duplicate_input_same_hash():
    from app.services.link_parser import parse
    samples = [s for s in SAMPLES if s[3]]
    hashes = {parse(s[0]).share_hash for s in samples}
    # 每个不同 share_id 一个 hash
    expected = {s[1].lower() for s in samples}
    assert len(hashes) == len({s[1] for s in samples})


def test_multiple_links_in_one_message():
    from app.services.link_parser import parse_all
    text = "两个 https://115.com/s/aaa111?password=p1 和 https://115.com/s/bbb222?password=p2"
    results = parse_all(text)
    assert len(results) == 2
    assert {r.share_id for r in results} == {"aaa111", "bbb222"}
