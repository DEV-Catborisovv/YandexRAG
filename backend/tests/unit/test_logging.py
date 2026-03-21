import logging
import json
from src.core.logging import JsonFormatter

def test_json_formatter_format():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="p",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None
    )
    record.context = {"user_id": 123}
    
    formatted = formatter.format(record)
    data = json.loads(formatted)
    
    assert data["message"] == "test message"
    assert data["context"]["user_id"] == 123
    assert "timestamp" in data
