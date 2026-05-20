import pytest
from app_v4.desktop.setup.validators import (
    validate_passphrase,
    validate_username,
    validate_password,
    validate_bind_host,
    validate_bind_port,
)


@pytest.mark.parametrize("value,confirm,expected_substring", [
    ("short", "short", "12 characters"),
    ("nouppercaseornumber!", "nouppercaseornumber!", "upper"),
    ("NoDigitsHere!!!", "NoDigitsHere!!!", "digit"),
    ("StrongP4ssphrase", "different", "match"),
    ("StrongP4ssphrase", "StrongP4ssphrase", None),
])
def test_validate_passphrase(value, confirm, expected_substring):
    error = validate_passphrase(value, confirm)
    if expected_substring is None:
        assert error is None
    else:
        assert expected_substring.lower() in (error or "").lower()


@pytest.mark.parametrize("value,expected_substring", [
    ("ab", "3"),
    ("1starts_digit", "letter"),
    ("has space", "alphanumeric"),
    ("admin", None),
    ("ops_admin-1", None),
])
def test_validate_username(value, expected_substring):
    error = validate_username(value)
    if expected_substring is None:
        assert error is None
    else:
        assert expected_substring.lower() in (error or "").lower()


@pytest.mark.parametrize("password,confirm,expected_substring", [
    ("short1A", "short1A", "8"),
    ("alllower1", "alllower1", "upper"),
    ("ALLUPPER1", "ALLUPPER1", "lower"),
    ("NoDigitsXX", "NoDigitsXX", "digit"),
    ("Goodpass1", "different", "match"),
    ("Goodpass1", "Goodpass1", None),
])
def test_validate_password(password, confirm, expected_substring):
    error = validate_password(password, confirm)
    if expected_substring is None:
        assert error is None
    else:
        assert expected_substring.lower() in (error or "").lower()


@pytest.mark.parametrize("value,is_valid", [
    ("127.0.0.1", True),
    ("0.0.0.0", True),
    ("192.168.10.5", True),
    ("999.0.0.1", False),
    ("256.1.1.1", False),
    ("hostname", True),
    ("with space", False),
    ("", False),
])
def test_validate_bind_host(value, is_valid):
    error = validate_bind_host(value)
    if is_valid:
        assert error is None
    else:
        assert error is not None


@pytest.mark.parametrize("value,is_valid", [
    ("8443", True),
    ("1024", True),
    ("65535", True),
    ("1023", False),
    ("65536", False),
    ("0", False),
    ("abc", False),
    ("", False),
])
def test_validate_bind_port(value, is_valid):
    error = validate_bind_port(value)
    if is_valid:
        assert error is None
    else:
        assert error is not None
