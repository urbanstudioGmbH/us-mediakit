from us_mediakit.core.svg import sanitize_svg


def test_removes_script_tag():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><rect/></svg>'
    result = sanitize_svg(svg)
    assert b"script" not in result
    assert b"alert" not in result


def test_removes_event_handler_attribute():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect onload="alert(1)"/></svg>'
    result = sanitize_svg(svg)
    assert b"onload" not in result
    assert b"alert" not in result


def test_removes_javascript_href():
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        b'<a xlink:href="javascript:alert(1)"><rect/></a></svg>'
    )
    result = sanitize_svg(svg)
    assert b"javascript" not in result


def test_removes_foreign_object():
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg">'
        b'<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">x</div></foreignObject>'
        b"</svg>"
    )
    result = sanitize_svg(svg)
    assert b"foreignObject" not in result


def test_strips_doctype_before_parsing():
    svg = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE svg [<!ENTITY xxe "boom">]>'
        b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    )
    result = sanitize_svg(svg)
    assert b"ENTITY" not in result


def test_keeps_harmless_same_document_reference():
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        b'<defs><rect id="r"/></defs><use xlink:href="#r"/></svg>'
    )
    result = sanitize_svg(svg)
    assert b"#r" in result
