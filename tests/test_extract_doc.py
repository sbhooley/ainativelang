"""core.EXTRACT returns text and links and does not run the document."""

from runtime.adapters.builtins import CoreBuiltinAdapter
from runtime.engine import RuntimeEngine
from runtime.extract_doc import extract_document

PAGE = (
    "<html><body><p>Hello</p>"
    '<a href="https://example.com/a">A</a>'
    '<a href="javascript:alert(1)">x</a>'
    "<script>alert(1)</script></body></html>"
)
FEED = (
    '<?xml version="1.0"?>'
    "<rss><channel><item><title>Hello</title>"
    "<link>https://example.com/a</link>"
    "<description>Body &amp; more</description>"
    "</item></channel></rss>"
)


def test_html_extract_drops_script_text_and_script_urls():
    out = extract_document(PAGE)
    assert out["text"] == "Hello A x"
    assert out["links"] == ["https://example.com/a"]
    assert "alert" not in out["text"]


def test_feed_extract_returns_title_description_and_link():
    out = extract_document(FEED)
    assert "Hello" in out["text"]
    assert "Body & more" in out["text"]
    assert out["links"] == ["https://example.com/a"]


def test_over_the_byte_cap_is_an_error_value_without_the_document():
    marker = "FILING-MARKER"
    out = extract_document(marker + ("x" * 1_000_000))
    assert out["error"]["code"] == "EXTRACT_LIMIT"
    assert marker not in str(out)


def test_doctype_entity_feed_does_not_parse():
    out = extract_document('<!DOCTYPE rss [<!ENTITY x "y">]><rss/>', "rss")
    assert out["error"]["code"] == "EXTRACT_PARSE"
    assert "ENTITY" not in out["error"]["message"]


def test_core_extract_verb_returns_the_same_shape():
    out = CoreBuiltinAdapter().call("EXTRACT", [PAGE], {})
    assert out["links"] == ["https://example.com/a"]
    assert "alert" not in out["text"]


def test_strict_graph_can_extract():
    source = """
S app core noop
L1:
  R core.EXTRACT page ->out
  J out
"""
    out = RuntimeEngine.from_code(source, strict=True, trace=False).run_label(
        "1", {"page": PAGE}
    )
    assert out["links"] == ["https://example.com/a"]
    assert "alert" not in out["text"]
