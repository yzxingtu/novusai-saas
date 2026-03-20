"""tenant_legal_html_has_meaningful_body / 法律 HTML 是否有可见正文"""

from app.utils.config_html_sanitize import tenant_legal_html_has_meaningful_body


def test_empty_and_placeholder_html_not_meaningful() -> None:
    assert tenant_legal_html_has_meaningful_body(None) is False
    assert tenant_legal_html_has_meaningful_body("") is False
    assert tenant_legal_html_has_meaningful_body("   ") is False
    assert tenant_legal_html_has_meaningful_body("<p></p>") is False
    assert tenant_legal_html_has_meaningful_body("<p><br></p>") is False
    assert tenant_legal_html_has_meaningful_body("<p>&nbsp;</p>") is False


def test_real_text_meaningful() -> None:
    assert tenant_legal_html_has_meaningful_body("<p>隐私政策正文内容</p>") is True
    assert tenant_legal_html_has_meaningful_body("纯文本") is True
