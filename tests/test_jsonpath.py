"""JSON Pointer and dot-path lookup."""

import pytest

from claimcheck.jsonpath import Missing, compile_path, resolve


def test_pointer_dot_and_whole_document():
    document = {
        "version": "0.1.0",
        "items": [{"name": "note"}],
        "a/b": 1,
        "~": 2,
        "01": "kept",
    }
    assert resolve(document, compile_path("/version")) == "0.1.0"
    assert resolve(document, compile_path("/items/0/name")) == "note"
    assert resolve(document, compile_path("/a~1b")) == 1
    assert resolve(document, compile_path("/~0")) == 2
    assert resolve(document, compile_path("/")) == document
    assert resolve(document, compile_path("$")) == document
    assert resolve(document, compile_path("$.items[0].name")) == "note"
    assert resolve(document, compile_path("items[0].name")) == "note"
    assert resolve(document["items"], compile_path("[0].name")) == "note"
    assert resolve(document, compile_path("01")) == "kept"


def test_missing_and_bad_syntax():
    document = {"items": [{"name": "note"}]}
    with pytest.raises(Missing):
        resolve(document, compile_path("/items/3"))
    with pytest.raises(Missing):
        resolve(document, compile_path("/nope"))
    with pytest.raises(Missing):
        resolve(document, compile_path("items.0.missing"))
    for expr in ("", "$.", "items.", "items[", "a..b", "$nope"):
        with pytest.raises(ValueError):
            compile_path(expr)
    with pytest.raises(ValueError):
        compile_path("/bad~2")
