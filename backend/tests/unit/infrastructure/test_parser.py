from src.infrastructure.utils.parser import parse_xml_river_response

def test_parser_valid_yandex_xml():
    xml = """
    <root>
        <doc>
            <title>Test Title</title>
            <snippet>Test Snippet Content</snippet>
            <url>https://test.com</url>
        </doc>
        <doc>
            <title>Second Result</title>
            <snippet>Another snippet</snippet>
            <url>https://second.com</url>
        </doc>
    </root>
    """
    results = parse_xml_river_response(xml)
    assert len(results) == 2
    assert results[0]["title"] == "Test Title"
    assert results[1]["url"] == "https://second.com"

def test_parser_empty_xml():
    assert parse_xml_river_response("") == []

def test_parser_malformed_xml():
    xml = "<doc><title>No closing tag"
    results = parse_xml_river_response(xml)
    assert isinstance(results, list)
