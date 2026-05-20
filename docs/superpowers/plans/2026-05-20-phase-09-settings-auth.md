# Phase 9 — Settings: Authentication (Token / Lockout / Password Policy)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configurable token lifetime, account lockout policy, and password policy. AuthService reads runtime values; login flow enforces lockout; password validators apply at create/reset paths.

**Architecture:**
- Backend storage: extend `runtime_settings.json` with an `auth` section. `core/runtime_settings.py` gains `AuthSettings` dataclass.
- `AuthService` accepts a `settings_provider: Callable[[], AuthSettings]` and reads token lifetime per-issue.
- Schema migration adds `User.failed_login_count`, `User.last_failed_login_at`, `User.locked_until`.
- `api/auth.py:login` enforces window/threshold/lock + audit events.
- `core/password_policy.py` provides validator; called from cli init, user create, password reset, plus exposed via API for the SPA to mirror policy.
- New endpoints: `GET/PATCH /system/auth-settings` and `POST /users/{id}/unlock`.
- Frontend: SettingsAuthSection with three sub-cards.

**Tech Stack:** SQLAlchemy 2 async, Pydantic v2, FastAPI, vitest, pytest.

**Spec reference:** `docs/superpowers/specs/2026-05-20-ncm-v4-production-completion-design.md` Section 9.

---

## Task 1: Schema migration for lockout columns

**Files:**
- Modify: `app_v4/data/models.py`
- Modify: `app_v4/data/db.py`
- Modify: `app_v4/tests/test_db_init.py`

- [ ] **Step 1: Failing test**

```python
@pytest.mark.asyncio
async def test_users_table_has_lockout_columns(tmp_path):
    db_url = f"sqlite+aiosqlite:///{(tmp_path / 'app.db').as_posix()}"
    engine = create_async_engine(db_url)
    await init_db(engine)
    async with engine.begin() as conn:
        cols = await conn.run_sync(lambda s: {c['name'] for c in inspect(s).get_columns('users')})
    assert 'failed_login_count' in cols
    assert 'last_failed_login_at' in cols
    assert 'locked_until' in cols
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Add columns**

`models.py` `User`:
```python
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    last_failed_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

`db.py` `_run_sqlite_migrations`:
```python
    await _add_column_if_missing(conn, "users", "failed_login_count", "INTEGER NOT NULL DEFAULT 0")
    await _add_column_if_missing(conn, "users", "last_failed_login_at", "DATETIME")
    await _add_column_if_missing(conn, "users", "locked_until", "DATETIME")
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/data/models.py app_v4/data/db.py app_v4/tests/test_db_init.py
git commit -m "feat(db): add lockout columns to users"
```

---

## Task 2: Extend `runtime_settings.py` with `AuthSettings`

**Files:**
- Modify: `app_v4/core/runtime_settings.py`
- Modify: `app_v4/tests/test_runtime_settings.py`

- [ ] **Step 1: Failing tests**

```python
def test_auth_defaults():
    rs = RuntimeSettings()
    assert rs.auth.access_token_minutes == 15
    assert rs.auth.refresh_token_days == 7
    assert rs.auth.lockout_threshold == 5
    assert rs.auth.lockout_window_minutes == 10
    assert rs.auth.lockout_duration_minutes == 30
    assert rs.auth.password_min_length == 8
    assert rs.auth.password_require_upper is True
    assert rs.auth.password_require_lower is True
    assert rs.auth.password_require_digit is True
    assert rs.auth.password_require_symbol is False


def test_save_load_round_trip_includes_auth(tmp_path):
    target = tmp_path / "rs.json"
    rs = RuntimeSettings(
        retention=RetentionSettings(),
        auth=AuthSettings(access_token_minutes=30, lockout_threshold=0),
    )
    save_runtime_settings(target, rs)
    loaded = load_runtime_settings(target)
    assert loaded.auth.access_token_minutes == 30
    assert loaded.auth.lockout_threshold == 0
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Implement**

```python
@dataclass(frozen=True)
class AuthSettings:
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    lockout_threshold: int = 5
    lockout_window_minutes: int = 10
    lockout_duration_minutes: int = 30
    password_min_length: int = 8
    password_require_upper: bool = True
    password_require_lower: bool = True
    password_require_digit: bool = True
    password_require_symbol: bool = False


@dataclass(frozen=True)
class RuntimeSettings:
    retention: RetentionSettings = field(default_factory=RetentionSettings)
    auth: AuthSettings = field(default_factory=AuthSettings)
```

Update `load_runtime_settings`:
```python
auth_data = data.get("auth", {})
return RuntimeSettings(
    retention=RetentionSettings(**{k: v for k, v in retention_data.items() if k in RetentionSettings.__dataclass_fields__}),
    auth=AuthSettings(**{k: v for k, v in auth_data.items() if k in AuthSettings.__dataclass_fields__}),
)
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/core/runtime_settings.py app_v4/tests/test_runtime_settings.py
git commit -m "feat(runtime-settings): add auth section with defaults"
```

---

## Task 3: `core/password_policy.py`

**Files:**
- Create: `app_v4/core/password_policy.py`
- Create: `app_v4/tests/test_password_policy.py`

- [ ] **Step 1: Failing tests**

```python
import pytest
from app_v4.core.password_policy import validate_password, PasswordPolicy


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
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Implement**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PasswordPolicy:
    min_length: int = 8
    require_upper: bool = True
    require_lower: bool = True
    require_digit: bool = True
    require_symbol: bool = False


def validate_password(password: str, policy: PasswordPolicy) -> str | None:
    if len(password) < policy.min_length:
        return f"Password must be at least {policy.min_length} characters"
    if policy.require_upper and not any(c.isupper() for c in password):
        return "Password must include an upper-case letter"
    if policy.require_lower and not any(c.islower() for c in password):
        return "Password must include a lower-case letter"
    if policy.require_digit and not any(c.isdigit() for c in password):
        return "Password must include a digit"
    if policy.require_symbol and password.isalnum():
        return "Password must include a symbol"
    return None
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/core/password_policy.py app_v4/tests/test_password_policy.py
git commit -m "feat(core): password_policy validator"
```

---

## Task 4: AuthService becomes settings-aware

**Files:**
- Modify: `app_v4/core/auth_service.py`
- Modify: `app_v4/service/runtime.py`
- Modify: `app_v4/tests/test_auth_service.py`

- [ ] **Step 1: Failing test**

```python
def test_access_token_uses_provider_for_minutes(tmp_path):
    from app_v4.core.auth_service import AuthService
    from app_v4.core.runtime_settings import AuthSettings

    minutes_holder = {"value": 15}
    def provider() -> AuthSettings:
        return AuthSettings(access_token_minutes=minutes_holder["value"])

    svc = AuthService(jwt_secret=b"x" * 32, settings_provider=provider)
    token = svc.issue_access_token(user_id=1, username="admin", role="admin")
    claims = svc.verify_access_token(token)

    issued_at = datetime.fromtimestamp(claims.expires_at.timestamp() - minutes_holder["value"] * 60, tz=timezone.utc)
    assert (claims.expires_at - issued_at).total_seconds() == minutes_holder["value"] * 60

    minutes_holder["value"] = 30
    token2 = svc.issue_access_token(user_id=1, username="admin", role="admin")
    claims2 = svc.verify_access_token(token2)
    assert (claims2.expires_at - claims.expires_at).total_seconds() >= 60
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Refactor `AuthService`**

```python
from typing import Callable
from app_v4.core.runtime_settings import AuthSettings

AuthSettingsProvider = Callable[[], AuthSettings]


class AuthService:
    def __init__(
        self,
        jwt_secret: bytes,
        settings_provider: AuthSettingsProvider,
    ):
        self.jwt_secret = jwt_secret
        self.settings_provider = settings_provider
        self.password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)

    def issue_access_token(self, user_id: int, username: str, role: str) -> str:
        auth = self.settings_provider()
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=auth.access_token_minutes)
        payload = {
            "sub": str(user_id), "username": username, "role": role,
            "iat": int(now.timestamp()), "exp": int(exp.timestamp()), "typ": "access",
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")
```

Adapt `Settings` parameter removed; existing callers in `runtime.py` and `cli.py` need to be updated. Create a default provider used at runtime:

```python
def make_default_provider(runtime_settings_path: Path) -> AuthSettingsProvider:
    def _provider():
        return load_runtime_settings(runtime_settings_path).auth
    return _provider
```

In `service/runtime.py:build_runtime`, build provider from `paths.data_dir / "runtime_settings.json"` and pass to `AuthService`.

In `ServiceRuntime.for_tests`, accept `auth_settings: AuthSettings | None = None` and pass `lambda: auth_settings or AuthSettings()` as provider.

In `cli.py` `init_command`, create a one-shot provider returning defaults (passing `lambda: AuthSettings()`).

- [ ] **Step 4: Update existing tests** that constructed `AuthService(settings, jwt_secret)` to use the new signature.

- [ ] **Step 5: Run, PASS.**

Run: `python -m pytest app_v4/tests/test_auth_service.py app_v4/tests/test_app_factory.py app_v4/tests/test_cli_init.py -v`

- [ ] **Step 6: Commit**

```bash
git add app_v4/core/auth_service.py app_v4/service/runtime.py app_v4/cli.py \
        app_v4/tests/test_auth_service.py
git commit -m "refactor(auth): AuthService reads token lifetime from provider"
```

---

## Task 5: Lockout enforcement in login flow

**Files:**
- Modify: `app_v4/data/repository.py`
- Modify: `app_v4/service/api/auth.py`
- Create: `app_v4/tests/test_auth_lockout.py`

- [ ] **Step 1: Failing tests**

```python
import pytest
from datetime import datetime, timezone
from app_v4.core.runtime_settings import AuthSettings


@pytest.mark.asyncio
async def test_repeated_failures_lock_account(client, runtime, seeded_user):
    runtime._auth_settings_override = AuthSettings(lockout_threshold=3, lockout_window_minutes=10, lockout_duration_minutes=15)
    for _ in range(3):
        r = await client.post("/api/v1/auth/login", json={"username": seeded_user["username"], "password": "wrong"})
        assert r.status_code == 401
    r = await client.post("/api/v1/auth/login", json={"username": seeded_user["username"], "password": seeded_user["password"]})
    assert r.status_code == 423


@pytest.mark.asyncio
async def test_threshold_zero_disables_lockout(client, runtime, seeded_user):
    runtime._auth_settings_override = AuthSettings(lockout_threshold=0)
    for _ in range(10):
        r = await client.post("/api/v1/auth/login", json={"username": seeded_user["username"], "password": "wrong"})
        assert r.status_code == 401
    r = await client.post("/api/v1/auth/login", json={"username": seeded_user["username"], "password": seeded_user["password"]})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_successful_login_resets_counter(client, runtime, seeded_user):
    for _ in range(2):
        await client.post("/api/v1/auth/login", json={"username": seeded_user["username"], "password": "wrong"})
    r = await client.post("/api/v1/auth/login", json={"username": seeded_user["username"], "password": seeded_user["password"]})
    assert r.status_code == 200
    # Now a new round of failures starts fresh
    for _ in range(2):
        await client.post("/api/v1/auth/login", json={"username": seeded_user["username"], "password": "wrong"})
    r = await client.post("/api/v1/auth/login", json={"username": seeded_user["username"], "password": seeded_user["password"]})
    assert r.status_code == 200
```

You may need to add an `_auth_settings_override` mechanism on the runtime test fixture; the settings_provider can read from it when set, otherwise use defaults.

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Implement login flow**

In `api/auth.py:login`:
```python
auth_cfg = runtime.auth_settings_provider()
now = datetime.now(timezone.utc)

if user.locked_until is not None and user.locked_until > now:
    await runtime.audit_writer.record(action="auth.login_blocked_locked", user_id=user.id, ip=ip)
    raise problem(423, "Locked", "Account temporarily locked")

if not runtime.auth_service.verify_password(payload.password, user.password_hash):
    if (
        user.last_failed_login_at is None
        or (now - user.last_failed_login_at) > timedelta(minutes=auth_cfg.lockout_window_minutes)
    ):
        user.failed_login_count = 1
    else:
        user.failed_login_count += 1
    user.last_failed_login_at = now
    if auth_cfg.lockout_threshold > 0 and user.failed_login_count >= auth_cfg.lockout_threshold:
        user.locked_until = now + timedelta(minutes=auth_cfg.lockout_duration_minutes)
        await runtime.audit_writer.record(action="auth.locked", user_id=user.id, ip=ip)
    await session.commit()
    await runtime.audit_writer.record(action="auth.login_failed", user_id=user.id, ip=ip)
    raise problem(401, "Unauthorized", "Invalid username or password")

# success branch — reset counters
user.failed_login_count = 0
user.last_failed_login_at = None
user.locked_until = None
```

Make sure `runtime.auth_settings_provider` is wired in `service/runtime.py`. Add it to `ServiceRuntime` dataclass.

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/api/auth.py app_v4/service/runtime.py \
        app_v4/data/repository.py app_v4/tests/test_auth_lockout.py
git commit -m "feat(auth): account lockout policy"
```

---

## Task 6: Password policy enforcement on user create + reset + cli

**Files:**
- Modify: `app_v4/service/api/users.py`
- Modify: `app_v4/cli.py`
- Modify: `app_v4/tests/test_users_api.py`

- [ ] **Step 1: Failing test**

```python
@pytest.mark.asyncio
async def test_create_user_rejects_weak_password(client, admin_token):
    r = await client.post(
        "/api/v1/users",
        json={"username": "newop", "password": "weak", "role": "operator"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422
    assert "8" in r.json()["detail"]
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Apply policy**

In `api/users.py:create_user` and `reset_password`:
```python
auth_cfg = runtime.auth_settings_provider()
policy = PasswordPolicy(
    min_length=auth_cfg.password_min_length,
    require_upper=auth_cfg.password_require_upper,
    require_lower=auth_cfg.password_require_lower,
    require_digit=auth_cfg.password_require_digit,
    require_symbol=auth_cfg.password_require_symbol,
)
error = validate_password(payload.password, policy)
if error:
    raise problem(422, "Unprocessable Entity", error)
```

In `cli.init_command`, use default `PasswordPolicy()` (runtime settings file may not exist yet at first init). Validate before hashing the admin password.

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/api/users.py app_v4/cli.py app_v4/tests/test_users_api.py
git commit -m "feat(auth): enforce password policy on create and reset"
```

---

## Task 7: `/system/auth-settings` GET/PATCH endpoints

**Files:**
- Modify: `app_v4/service/api/system.py`
- Modify: `app_v4/tests/test_system_api.py`

- [ ] **Step 1: Failing tests**

```python
@pytest.mark.asyncio
async def test_get_auth_settings_admin_only(client, admin_token, viewer_token):
    r = await client.get("/api/v1/system/auth-settings", headers={"Authorization": f"Bearer {viewer_token}"})
    assert r.status_code == 403
    r = await client.get("/api/v1/system/auth-settings", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["access_token_minutes"] == 15


@pytest.mark.asyncio
async def test_patch_auth_settings_persists_and_validates(client, admin_token):
    r = await client.patch(
        "/api/v1/system/auth-settings",
        json={"access_token_minutes": 4},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422

    r = await client.patch(
        "/api/v1/system/auth-settings",
        json={"access_token_minutes": 30, "lockout_threshold": 0},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["access_token_minutes"] == 30
    assert r.json()["lockout_threshold"] == 0
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Implement**

```python
class AuthSettingsResponse(BaseModel):
    access_token_minutes: int
    refresh_token_days: int
    lockout_threshold: int
    lockout_window_minutes: int
    lockout_duration_minutes: int
    password_min_length: int
    password_require_upper: bool
    password_require_lower: bool
    password_require_digit: bool
    password_require_symbol: bool


class AuthSettingsPatch(BaseModel):
    access_token_minutes: int | None = Field(default=None, ge=5, le=1440)
    refresh_token_days: int | None = Field(default=None, ge=1, le=30)
    lockout_threshold: int | None = Field(default=None, ge=0, le=20)
    lockout_window_minutes: int | None = Field(default=None, ge=1, le=60)
    lockout_duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    password_min_length: int | None = Field(default=None, ge=6, le=128)
    password_require_upper: bool | None = None
    password_require_lower: bool | None = None
    password_require_digit: bool | None = None
    password_require_symbol: bool | None = None


@router.get("/auth-settings", response_model=AuthSettingsResponse)
async def get_auth_settings(
    runtime: ServiceRuntime = Depends(get_runtime),
    _user: AccessClaims = Depends(require_role("admin")),
) -> AuthSettingsResponse:
    paths = resolve_paths(runtime.settings)
    rs = load_runtime_settings(paths.data_dir / "runtime_settings.json")
    return AuthSettingsResponse(**asdict(rs.auth))


@router.patch("/auth-settings", response_model=AuthSettingsResponse)
async def patch_auth_settings(
    payload: AuthSettingsPatch,
    request: Request,
    runtime: ServiceRuntime = Depends(get_runtime),
    user: AccessClaims = Depends(require_role("admin")),
) -> AuthSettingsResponse:
    paths = resolve_paths(runtime.settings)
    target = paths.data_dir / "runtime_settings.json"
    current = load_runtime_settings(target)
    updates = payload.model_dump(exclude_none=True)
    new_auth = replace(current.auth, **updates)
    save_runtime_settings(target, replace(current, auth=new_auth))
    await runtime.audit_writer.record(
        action="system.auth_settings_updated",
        user_id=user.user_id,
        ip=request.client.host if request.client else None,
        detail={"changes": updates},
    )
    return AuthSettingsResponse(**asdict(new_auth))
```

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/api/system.py app_v4/tests/test_system_api.py
git commit -m "feat(api): /system/auth-settings GET/PATCH"
```

---

## Task 8: `POST /users/{id}/unlock`

**Files:**
- Modify: `app_v4/service/api/users.py`
- Modify: `app_v4/tests/test_users_api.py`

- [ ] **Step 1: Failing test**

```python
@pytest.mark.asyncio
async def test_admin_unlock_clears_lock(client, admin_token, locked_user_id, runtime):
    r = await client.post(
        f"/api/v1/users/{locked_user_id}/unlock",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Implement endpoint** that sets `failed_login_count=0`, `last_failed_login_at=None`, `locked_until=None`, audit `user.unlock_by_admin`.

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Commit**

```bash
git add app_v4/service/api/users.py app_v4/tests/test_users_api.py
git commit -m "feat(users): admin unlock endpoint"
```

---

## Task 9: SettingsAuthSection UI

**Files:**
- Create: `app_v4/web/src/pages/settings/SettingsAuthSection.tsx`
- Create: `app_v4/web/src/pages/settings/SettingsAuthSection.test.tsx`
- Modify: `app_v4/web/src/api/hooks.ts`
- Modify: `app_v4/web/src/api/types.ts`
- Modify: `app_v4/web/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Add types**

```ts
export interface AuthSettings {
  access_token_minutes: number;
  refresh_token_days: number;
  lockout_threshold: number;
  lockout_window_minutes: number;
  lockout_duration_minutes: number;
  password_min_length: number;
  password_require_upper: boolean;
  password_require_lower: boolean;
  password_require_digit: boolean;
  password_require_symbol: boolean;
}
```

- [ ] **Step 2: Add hooks**

```ts
export function useAuthSettings() {
  return useQuery({ queryKey: ['system', 'auth-settings'],
    queryFn: async () => (await api.get<AuthSettings>('/system/auth-settings')).data });
}
export function usePatchAuthSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: Partial<AuthSettings>) =>
      (await api.patch<AuthSettings>('/system/auth-settings', input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['system', 'auth-settings'] }),
  });
}
```

- [ ] **Step 3: Failing test**

Create `app_v4/web/src/pages/settings/SettingsAuthSection.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsAuthSection } from './SettingsAuthSection';

const mutate = vi.fn();

vi.mock('../../api/hooks', () => ({
  useAuthSettings: () => ({
    data: {
      access_token_minutes: 15,
      refresh_token_days: 7,
      lockout_threshold: 5,
      lockout_window_minutes: 10,
      lockout_duration_minutes: 30,
      password_min_length: 8,
      password_require_upper: true,
      password_require_lower: true,
      password_require_digit: true,
      password_require_symbol: false,
    },
    isLoading: false,
  }),
  usePatchAuthSettings: () => ({ mutate, isPending: false }),
}));

describe('SettingsAuthSection', () => {
  it('renders three save buttons (one per card)', () => {
    render(<SettingsAuthSection />);
    expect(screen.getAllByRole('button', { name: /save/i })).toHaveLength(3);
  });

  it('Token card Save sends only the changed token field', async () => {
    const user = userEvent.setup();
    render(<SettingsAuthSection />);
    const access = screen.getByLabelText(/Access token/i);
    await user.clear(access);
    await user.type(access, '30');
    const tokenCard = access.closest('article')!;
    const save = tokenCard.querySelector('button')! as HTMLButtonElement;
    await user.click(save);
    expect(mutate).toHaveBeenCalledWith(
      { access_token_minutes: 30 },
      expect.anything(),
    );
  });

  it('Password card Save sends only the changed password field', async () => {
    const user = userEvent.setup();
    render(<SettingsAuthSection />);
    const symbol = screen.getByLabelText(/Require symbol/i);
    await user.click(symbol);
    const card = symbol.closest('article')!;
    const save = card.querySelector('button')! as HTMLButtonElement;
    await user.click(save);
    expect(mutate).toHaveBeenLastCalledWith(
      { password_require_symbol: true },
      expect.anything(),
    );
  });
});
```

- [ ] **Step 4: Implement component**

Create `app_v4/web/src/pages/settings/SettingsAuthSection.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { useAuthSettings, usePatchAuthSettings } from '../../api/hooks';
import type { AuthSettings } from '../../api/types';

type CardKey = 'token' | 'lockout' | 'password';

const FIELDS_BY_CARD: Record<CardKey, (keyof AuthSettings)[]> = {
  token: ['access_token_minutes', 'refresh_token_days'],
  lockout: ['lockout_threshold', 'lockout_window_minutes', 'lockout_duration_minutes'],
  password: [
    'password_min_length',
    'password_require_upper',
    'password_require_lower',
    'password_require_digit',
    'password_require_symbol',
  ],
};

const FIELD_LABEL: Record<keyof AuthSettings, string> = {
  access_token_minutes: 'Access token (minutes)',
  refresh_token_days: 'Refresh token (days)',
  lockout_threshold: 'Failed attempts threshold (0 = disabled)',
  lockout_window_minutes: 'Failure window (minutes)',
  lockout_duration_minutes: 'Lockout duration (minutes)',
  password_min_length: 'Min length',
  password_require_upper: 'Require uppercase',
  password_require_lower: 'Require lowercase',
  password_require_digit: 'Require digit',
  password_require_symbol: 'Require symbol',
};

export function SettingsAuthSection() {
  const { data } = useAuthSettings();
  const patch = usePatchAuthSettings();
  const [draft, setDraft] = useState<AuthSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) setDraft({ ...data });
  }, [data]);

  if (!draft || !data) return <p>Loading…</p>;

  function dirtyKeys(card: CardKey): (keyof AuthSettings)[] {
    return FIELDS_BY_CARD[card].filter((key) => draft![key] !== data![key]);
  }

  function saveCard(card: CardKey) {
    if (!data || !draft) return;
    setError(null);
    const updates: Partial<AuthSettings> = {};
    for (const key of dirtyKeys(card)) {
      (updates as Record<string, AuthSettings[keyof AuthSettings]>)[key] = draft[key];
    }
    patch.mutate(updates, {
      onError: (err: unknown) => setError(err instanceof Error ? err.message : 'Save failed'),
    });
  }

  function setField<K extends keyof AuthSettings>(key: K, value: AuthSettings[K]) {
    setDraft({ ...draft!, [key]: value });
  }

  function renderField(key: keyof AuthSettings) {
    const value = draft![key];
    if (typeof value === 'boolean') {
      return (
        <label key={key} className="settings-field">
          <input
            type="checkbox"
            checked={value}
            onChange={(event) => setField(key, event.target.checked as AuthSettings[typeof key])}
          />
          <span>{FIELD_LABEL[key]}</span>
        </label>
      );
    }
    return (
      <label key={key} className="settings-field">
        <span>{FIELD_LABEL[key]}</span>
        <input
          type="number"
          value={value as number}
          onChange={(event) => setField(key, Number(event.target.value) as AuthSettings[typeof key])}
        />
      </label>
    );
  }

  function renderCard(card: CardKey, title: string) {
    const dirty = dirtyKeys(card);
    return (
      <article className="settings-card">
        <h3>{title}</h3>
        {FIELDS_BY_CARD[card].map(renderField)}
        <button onClick={() => saveCard(card)} disabled={dirty.length === 0 || patch.isPending}>
          {patch.isPending ? 'Saving…' : 'Save'}
        </button>
      </article>
    );
  }

  return (
    <section>
      <h2>Authentication</h2>
      {error && <div role="alert" className="settings-error">{error}</div>}
      {renderCard('token', 'Token Lifetime')}
      {renderCard('lockout', 'Account Lockout')}
      {renderCard('password', 'Password Policy')}
    </section>
  );
}
```

- [ ] **Step 5: Add tab to `SettingsPage`**

```tsx
const TABS = [
  { id: 'service', label: 'Service', section: <SettingsServiceSection /> },
  { id: 'retention', label: 'Retention', section: <SettingsRetentionSection /> },
  { id: 'auth', label: 'Authentication', section: <SettingsAuthSection /> },
  { id: 'about', label: 'About', section: <SettingsAboutSection /> },
];
```

- [ ] **Step 6: Run all suites + commit**

```bash
git add app_v4/web/src/pages/settings/SettingsAuthSection.tsx \
        app_v4/web/src/pages/settings/SettingsAuthSection.test.tsx \
        app_v4/web/src/api/hooks.ts app_v4/web/src/api/types.ts \
        app_v4/web/src/pages/SettingsPage.tsx
git commit -m "feat(settings): authentication section with three cards"
```

---

## Task 10: Verify + bundle

- [ ] Backend pytest, frontend vitest, vite build, PyInstaller rebuild — all green.
