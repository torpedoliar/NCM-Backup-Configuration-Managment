from app_v4.service.main import app_import_string, uvicorn_kwargs


def test_uvicorn_import_string_is_stable():
    assert app_import_string() == "app_v4.service.main:create_runtime_app"


def test_uvicorn_kwargs_uses_settings(test_settings):
    kwargs = uvicorn_kwargs(test_settings)

    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8443
    assert kwargs["factory"] is True
