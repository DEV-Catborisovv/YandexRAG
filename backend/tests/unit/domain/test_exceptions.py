from src.domain.exceptions import AppException, ExternalAPIException

def test_app_exception_context():
    exc = AppException("msg", context={"id": 1})
    assert exc.message == "msg"
    assert exc.context["id"] == 1

def test_external_api_exception():
    exc = ExternalAPIException("Service", 404, "Not Found")
    assert exc.service == "Service"
    assert exc.status_code == 404
    assert "Not Found" in str(exc)
