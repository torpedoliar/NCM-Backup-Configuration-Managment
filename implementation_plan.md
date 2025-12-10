# Implementation Plan - Web Smart Switch Support

## Goal
Add support for backing up Allied Telesis WebSmart switches (FS750, GS950 series) via HTTP scraping, as these devices have limited CLI capabilities.

## User Review Required
> [!IMPORTANT]
> **Protocol Name**: The new protocol will be labeled "Web Smart" in the UI but stored as `http` in the database.
> **Port Default**: Default port for Web Smart will be **80**.
> **Login Logic**: The implementation will use a generic login flow (POST to `/login.cgi` or similar) based on common WebSmart patterns. This might need adjustment for specific firmware versions.

## Proposed Changes

### UI Layer
#### [MODIFY] [inventory_view.py](file:///d:/+SYNO+/Home/1.%20Project%20Windsurf/Test%20Project/app/ui/inventory_view.py)
- Add "Web Smart" Radiobutton to `SwitchDialog`.
- Update `on_protocol_change` to set default port to 80 for `http`.
- Update `_batch_import` to validate `http` protocol.

### Network Layer
#### [NEW] [web_smart_client.py](file:///d:/+SYNO+/Home/1.%20Project%20Windsurf/Test%20Project/app/net/web_smart_client.py)
- Create `WebSmartClient` class.
- Implement `login`, `download_config`, `logout` methods using `requests`.
- Handle session management and error checking.

#### [MODIFY] [runner.py](file:///d:/+SYNO+/Home/1.%20Project%20Windsurf/Test%20Project/app/net/runner.py)
- Import `WebSmartClient`.
- Update `execute_backup` to dispatch `http` protocol to `_execute_http`.
- Add `_execute_http` method.

### Dependencies
#### [MODIFY] [requirements.txt](file:///d:/+SYNO+/Home/1.%20Project%20Windsurf/Test%20Project/requirements.txt)
- Add `requests>=2.31.0`
- Add `beautifulsoup4>=4.12.0` (for parsing login forms/tokens)

## Verification Plan

### Automated Tests
- Create a test script `tests/test_web_smart.py` to mock the HTTP server and verify the client logic.

### Manual Verification
1.  **UI Check**: Open "Add Switch" dialog, verify "Web Smart" option exists and sets port to 80.
2.  **Import Check**: Try importing a CSV with `protocol,http`.
3.  **Execution**: (Requires device) Run backup against a WebSmart switch.
