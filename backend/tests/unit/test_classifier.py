from tests.fixtures.filenames import SAMPLES


def test_classify_all_samples():
    from app.services.classifier import classify
    for files, expected in SAMPLES:
        result = classify(files)
        assert result == expected, f"file_list={files} expected={expected} got={result}"


def test_classify_empty_returns_uncategorized():
    """空列表应返回 _未分类。"""
    from app.services.classifier import classify
    assert classify([]) == "_未分类"
