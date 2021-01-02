from lemonade_soapbox.helpers import JSONEncoder, truncate_html


def test_truncate_html(app):
    # Valid input
    test_html = """<p>Sed ut perspiciatis unde omnis iste natus error sit
    voluptatem accusantium doloremque laudantium, totam rem aperiam,
    eaque ipsa quae ab illo <strong class="blue">inventore veritatis</strong> et quasi architecto
    beatae vitae dicta sunt explicabo.</p>"""

    # Test passage is too short at default length
    truncated = truncate_html(test_html)
    assert str(truncated) == test_html

    # Shorter max length causes truncation
    truncated = truncate_html(test_html, 5)
    assert str(truncated) == "<p>Sed ut perspiciatis unde omnis…</p>"

    invalid_html = "<spa<><>>>><&#9;<p>Oops</span></p>"
    truncated = truncate_html(invalid_html)
