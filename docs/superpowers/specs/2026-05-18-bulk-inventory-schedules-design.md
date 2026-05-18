# Bulk Inventory and Schedule Operations Design

## Goal

Add bulk workflows to the existing Inventory and Schedules tabs without introducing a new tab or service layer. The UI should let operators import many switches, create schedules for many switches, and apply delete/enable/disable/start-now actions to multiple selected rows.

## Inventory tab

- Enable multi-row selection on the inventory `Treeview`.
- Keep the existing `Batch Import` CSV workflow and strengthen it:
  - CSV format: `name,ip,protocol,port,credential_name,notes`.
  - Required fields: `name`, `ip`, `credential_name`.
  - Default protocol: `ssh`.
  - Default port by protocol: SSH `22`, Telnet `23`, WebSmart/WebSmart V2 `80`.
  - Valid protocols: `ssh`, `telnet`, `websmart`, `websmart-v2`.
  - Valid port range: `1..65535`.
  - `credential_name` must match an existing credential.
- Add a `Paste Bulk` dialog that accepts the same comma-separated format as CSV. The first line may be a header; if no header is present, columns follow the documented order.
- Detect duplicate switches by matching existing `name` or `ip`.
- When duplicates exist, ask once per import whether to skip duplicates or update existing records.
- Bulk delete should delete all selected switches after one confirmation that shows count and a short preview of names.
- Bulk `Get Data` should run for all selected switches, reuse the existing parallel backup behavior, and skip switches already in `active_backups`.

## Schedules tab

- Enable multi-row selection on the schedules `Treeview`.
- Add `Bulk Add` schedule action:
  - Dialog lists all switches with multi-select/checklist behavior.
  - One schedule configuration is applied to every selected switch.
  - It reuses the existing interval/daily/weekly/monthly schedule controls.
- Add schedule CSV import:
  - CSV format: `switch_name,schedule_type,interval_minutes,hour,minute,enabled`.
  - `switch_name` must match an existing switch.
  - `schedule_type` accepts `interval`, `daily`, `weekly`, `monthly`.
  - For interval schedules, `interval_minutes` is required and must be `1..43200`.
  - For daily/weekly/monthly schedules, store interval as existing app conventions: daily `1440`, weekly `10080`, monthly `43200`.
  - `hour` must be `0..23`; `minute` must be `0..59`.
  - `enabled` defaults to true when omitted.
- Duplicate schedule definition is `switch_id + interval_minutes + schedule_hour + schedule_minute`.
- When duplicates exist, ask once per import whether to skip duplicates or update existing records.
- Bulk delete should delete all selected schedules, remove each scheduler job, and continue if one row fails.
- Bulk enable should enable all selected schedules in DB, resume scheduler jobs when present, and add missing scheduler jobs when needed.
- Bulk disable should disable all selected schedules in DB and pause scheduler jobs when present.
- Bulk start now should keep the existing sequential background execution model and apply it to all selected schedules.

## Error handling and feedback

- Parse and validate all rows before writing changes.
- Apply valid rows in one repository session where practical.
- Continue bulk row operations after individual failures, then show a summary.
- Summary includes counts: created/imported, updated, skipped, failed.
- Show the first 10 row errors in a messagebox and write full details to the existing console/log where available.
- Confirmation dialogs should show counts and a short item preview to avoid very large popups.

## Testing and verification

- Add focused unit tests for pure parsing/validation helpers where possible.
- Run `python -m unittest discover app/tests/`.
- Run `python -m py_compile app/main.py`.
- Manual UI smoke test:
  - import switches from CSV,
  - paste switches from text,
  - bulk add schedules for multiple switches,
  - import schedules from CSV,
  - select multiple inventory rows and run delete/get data,
  - select multiple schedule rows and run delete/enable/disable/start now.

## Out of scope

- New dedicated bulk operations tab.
- New service-layer abstraction for this change.
- Creating credentials during switch import.
- Parallel schedule `Start Now`; it remains sequential to avoid overloading devices.
