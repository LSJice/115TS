from tests.fixtures.filenames import SAMPLES


def test_classify_all_samples():
    from app.services.classifier import classify
    for files, expected in SAMPLES:
        result = classify(files)
        assert result == expected, f"file_list={files} expected={expected} got={result}"
