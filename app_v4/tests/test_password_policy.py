import pytest

from app_v4.core.password_policy import PasswordPolicy, validate_password


@pytest.mark.parametrize("policy_overrides,password,expected_substring", [
    ({}, "short", "8"),
    ({}, "alllower1", "upper"),
    ({}, "ALLUPPER1", "lower"),
    ({}, "NoDigitsAA", "digit"),
    ({}, "Goodpass1", None),
    ({"require_symbol": True}, "Goodpass1", "symbol"),
    ({"require_symbol": True}, "Goodpass1!", None),
    ({"min_length": 12}, "Short11A", "12"),
])
def test_validate_password(policy_overrides, password, expected_substring):
    policy = PasswordPolicy(**policy_overrides)
    error = validate_password(password, policy)
    if expected_substring is None:
        assert error is None
    else:
        assert expected_substring.lower() in (error or "").lower()
