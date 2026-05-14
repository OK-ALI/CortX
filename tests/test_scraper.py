from backend.scraper.bs4_parser import extract_visible_text


def test_extract_visible_text_removes_script_and_nav() -> None:
    html = """
    <html>
        <head><script>var x = 1;</script></head>
        <body>
            <nav>menu</nav>
            <main><p>Hello world from Cortx scraper parser.</p></main>
        </body>
    </html>
    """
    text = extract_visible_text(html)

    assert "Hello world" in text
    assert "menu" not in text
    assert "var x" not in text
