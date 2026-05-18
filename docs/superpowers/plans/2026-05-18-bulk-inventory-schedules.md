# Bulk Inventory and Schedule Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bulk switch inventory import/actions and bulk schedule creation/import/actions to the existing tkinter tabs.

**Architecture:** Keep the feature inside the existing `InventoryView` and `SchedulesView` files, matching the approved UI-only approach. Add pure parsing helpers at module level so CSV/paste behavior is testable without opening tkinter dialogs, then wire helpers into existing toolbar actions.

**Tech Stack:** Python 3.11+, tkinter/ttkbootstrap, SQLAlchemy repository pattern, unittest, APScheduler-backed `ScheduleService`.

---

## File Structure

- Modify: `app/ui/inventory_view.py`
  - Add switch bulk parsing helpers.
  - Enable multi-select inventory table.
  - Add paste import button/dialog.
  - Replace CSV import internals with shared bulk apply logic.
  - Extend delete and get-data actions to selected rows.
- Modify: `app/ui/schedules_view.py`
  - Add schedule bulk parsing helpers.
  - Enable multi-select schedule table.
  - Add bulk add and CSV import toolbar actions.
  - Extend schedule dialog for multi-switch bulk creation.
  - Extend delete/enable/disable/start-now actions to selected rows.
- Create: `app/tests/test_bulk_operations.py`
  - Unit tests for switch import parser.
  - Unit tests for schedule import parser.
- No new service layer and no new application tab.
- Do not create git commits unless the user explicitly authorizes commits in the execution session. Where this plan says checkpoint, use `rtk git diff` and wait for user permission before committing.

---

### Task 1: Add switch bulk parser tests

**Files:**
- Create: `app/tests/test_bulk_operations.py`
- Modify later: `app/ui/inventory_view.py`

- [ ] **Step 1: Write failing switch parser tests**

Create `app/tests/test_bulk_operations.py` with this initial content:

```python
"""Tests for bulk inventory and schedule parsing helpers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.ui.inventory_view import parse_switch_bulk_text


class TestSwitchBulkParsing(unittest.TestCase):
    def test_parse_switch_csv_with_header(self):
        text = "name,ip,protocol,port,credential_name,notes\nSW1,192.168.1.10,ssh,22,admin,Core switch\n"

        result = parse_switch_bulk_text(text)

        self.assertEqual([], result.errors)
        self.assertEqual(1, len(result.rows))
        row = result.rows[0]
        self.assertEqual(2, row.row_num)
        self.assertEqual("SW1", row.name)
        self.assertEqual("192.168.1.10", row.ip)
        self.assertEqual("ssh", row.protocol)
        self.assertEqual(22, row.port)
        self.assertEqual("admin", row.credential_name)
        self.assertEqual("Core switch", row.notes)

    def test_parse_switch_csv_without_header_uses_defaults(self):
        text = "SW2,192.168.1.11,, ,ops,Access switch\n"

        result = parse_switch_bulk_text(text)

        self.assertEqual([], result.errors)
        self.assertEqual(1, len(result.rows))
        row = result.rows[0]
        self.assertEqual(1, row.row_num)
        self.assertEqual("SW2", row.name)
        self.assertEqual("ssh", row.protocol)
        self.assertEqual(22, row.port)
        self.assertEqual("ops", row.credential_name)
        self.assertEqual("Access switch", row.notes)

    def test_parse_switch_csv_reports_invalid_rows(self):
        text = "name,ip,protocol,port,credential_name,notes\n,192.168.1.12,ssh,22,admin,Missing name\nSW3,,ssh,22,admin,Missing ip\nSW4,192.168.1.13,bad,22,admin,Bad protocol\nSW5,192.168.1.14,ssh,70000,admin,Bad port\nSW6,192.168.1.15,ssh,22,,Missing credential\n"

        result = parse_switch_bulk_text(text)

        self.assertEqual([], result.rows)
        self.assertEqual(5, len(result.errors))
        self.assertIn("Row 2: Missing switch name", result.errors)
        self.assertIn("Row 3: Missing IP address", result.errors)
        self.assertIn("Row 4: Invalid protocol 'bad'", result.errors)
        self.assertIn("Row 5: Invalid port '70000'", result.errors)
        self.assertIn("Row 6: Missing credential name", result.errors)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run switch parser tests to verify RED**

Run:

```powershell
rtk python -m unittest app.tests.test_bulk_operations.TestSwitchBulkParsing
```

Expected: FAIL with import error like `cannot import name 'parse_switch_bulk_text'`.

- [ ] **Step 3: Checkpoint**

Run:

```powershell
rtk git diff -- app/tests/test_bulk_operations.py
```

Expected: new test file shown. Do not commit unless user explicitly approved commits.

---

### Task 2: Implement switch bulk parser

**Files:**
- Modify: `app/ui/inventory_view.py`
- Test: `app/tests/test_bulk_operations.py`

- [ ] **Step 1: Add imports and parser dataclasses**

In `app/ui/inventory_view.py`, replace the import block near the top with these imports, preserving existing imports:

```python
"""Inventory view for managing switches"""
import logging
import threading
import asyncio
import time
import csv
import io
from dataclasses import dataclass
from tkinter import messagebox, END
from queue import Queue
from typing import List
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
```

Add this code after `logger = logging.getLogger(__name__)`:

```python
SWITCH_BULK_COLUMNS = ("name", "ip", "protocol", "port", "credential_name", "notes")
VALID_SWITCH_PROTOCOLS = {"ssh", "telnet", "websmart", "websmart-v2"}


@dataclass
class SwitchBulkRow:
    row_num: int
    name: str
    ip: str
    protocol: str
    port: int
    credential_name: str
    notes: str


@dataclass
class SwitchBulkParseResult:
    rows: List[SwitchBulkRow]
    errors: List[str]


def _default_switch_port(protocol: str) -> int:
    if protocol == "telnet":
        return 23
    if protocol in {"websmart", "websmart-v2"}:
        return 80
    return 22


def _is_switch_header(values: List[str]) -> bool:
    normalized = {value.strip().lower() for value in values}
    return "name" in normalized and "ip" in normalized


def _switch_record_from_values(values: List[str]) -> dict:
    return {
        column: values[index].strip() if index < len(values) else ""
        for index, column in enumerate(SWITCH_BULK_COLUMNS)
    }


def parse_switch_bulk_text(text: str) -> SwitchBulkParseResult:
    csv_rows = [
        row for row in csv.reader(io.StringIO(text))
        if any(cell.strip() for cell in row)
    ]
    if not csv_rows:
        return SwitchBulkParseResult(rows=[], errors=["No rows found"])

    has_header = _is_switch_header(csv_rows[0])
    header = [cell.strip().lower() for cell in csv_rows[0]] if has_header else []
    data_rows = csv_rows[1:] if has_header else csv_rows
    first_row_num = 2 if has_header else 1

    parsed_rows = []
    errors = []

    for offset, values in enumerate(data_rows):
        row_num = first_row_num + offset
        if has_header:
            record = {
                header[index]: values[index].strip() if index < len(values) else ""
                for index in range(len(header))
            }
        else:
            record = _switch_record_from_values(values)

        name = record.get("name", "").strip()
        ip = record.get("ip", "").strip()
        protocol = record.get("protocol", "ssh").strip().lower() or "ssh"
        port_text = record.get("port", "").strip()
        credential_name = record.get("credential_name", "").strip()
        notes = record.get("notes", "").strip()

        if not name:
            errors.append(f"Row {row_num}: Missing switch name")
            continue
        if not ip:
            errors.append(f"Row {row_num}: Missing IP address")
            continue
        if not credential_name:
            errors.append(f"Row {row_num}: Missing credential name")
            continue
        if protocol not in VALID_SWITCH_PROTOCOLS:
            errors.append(f"Row {row_num}: Invalid protocol '{protocol}'")
            continue

        if port_text:
            try:
                port = int(port_text)
            except ValueError:
                errors.append(f"Row {row_num}: Invalid port '{port_text}'")
                continue
            if not 1 <= port <= 65535:
                errors.append(f"Row {row_num}: Invalid port '{port_text}'")
                continue
        else:
            port = _default_switch_port(protocol)

        parsed_rows.append(SwitchBulkRow(
            row_num=row_num,
            name=name,
            ip=ip,
            protocol=protocol,
            port=port,
            credential_name=credential_name,
            notes=notes,
        ))

    return SwitchBulkParseResult(rows=parsed_rows, errors=errors)
```

- [ ] **Step 2: Run switch parser tests to verify GREEN**

Run:

```powershell
rtk python -m unittest app.tests.test_bulk_operations.TestSwitchBulkParsing
```

Expected: PASS.

- [ ] **Step 3: Run existing tests for regression check**

Run:

```powershell
rtk python -m unittest discover app/tests/
```

Expected: PASS.

- [ ] **Step 4: Checkpoint**

Run:

```powershell
rtk git diff -- app/ui/inventory_view.py app/tests/test_bulk_operations.py
```

Expected: parser helpers and parser tests shown. Do not commit unless user explicitly approved commits.

---

### Task 3: Wire inventory CSV, paste import, multi-delete, and multi-get-data

**Files:**
- Modify: `app/ui/inventory_view.py`
- Test: manual UI smoke plus existing unittest suite

- [ ] **Step 1: Enable multi-select and add Paste Bulk button**

In `InventoryView._create_ui`, change the `Treeview` creation to include `selectmode="extended"`:

```python
self.tree = ttk.Treeview(
    table_frame,
    columns=columns,
    show="headings",
    height=15,
    selectmode="extended"
)
```

After the existing `Batch Import` button block, add:

```python
ttk.Button(
    toolbar,
    text="📋 Paste Bulk",
    command=self._paste_bulk_import,
    bootstyle=SUCCESS
).pack(side=LEFT, padx=5)
```

- [ ] **Step 2: Add selection and summary helpers inside `InventoryView`**

Add these methods inside `class InventoryView`, before `_add_switch`:

```python
    def _get_selected_switch_rows(self):
        rows = []
        for item in self.tree.selection():
            values = self.tree.item(item)['values']
            rows.append({
                'id': int(values[0]),
                'name': values[1],
                'ip': values[2],
                'protocol': str(values[3]).lower(),
                'port': int(values[4]),
            })
        return rows

    def _format_name_preview(self, names):
        preview = ", ".join(names[:8])
        if len(names) > 8:
            preview += f", ... and {len(names) - 8} more"
        return preview

    def _format_bulk_result(self, title, created=0, updated=0, skipped=0, failed=0, errors=None):
        errors = errors or []
        message = (
            f"{title}\n\n"
            f"Created: {created}\n"
            f"Updated: {updated}\n"
            f"Skipped: {skipped}\n"
            f"Failed: {failed}"
        )
        if errors:
            message += "\n\nErrors:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                message += f"\n... and {len(errors) - 10} more errors"
        return message
```

- [ ] **Step 3: Add duplicate prompt and apply helper inside `InventoryView`**

Add these methods inside `class InventoryView`, before `_batch_import`:

```python
    def _ask_duplicate_mode(self, duplicate_count, item_label):
        result = Messagebox.yesno(
            f"Found {duplicate_count} duplicate {item_label}.\n\n"
            "Choose Yes to update existing records.\n"
            "Choose No to skip duplicates.",
            "Duplicates Found"
        )
        return "update" if result == "Yes" else "skip"

    def _import_switch_bulk_text(self, text, source_name):
        parse_result = parse_switch_bulk_text(text)
        errors = list(parse_result.errors)
        if not parse_result.rows:
            Messagebox.show_warning(
                self._format_bulk_result(f"No switches imported from {source_name}.", failed=len(errors), errors=errors),
                "Import Complete"
            )
            return

        created = 0
        updated = 0
        skipped = 0
        duplicate_count = 0

        try:
            with Repository() as repo:
                credentials = {cred.name: cred.id for cred in repo.list_credentials()}
                switches = repo.list_switches()
                by_name = {switch.name: switch for switch in switches}
                by_ip = {switch.ip: switch for switch in switches}

                for row in parse_result.rows:
                    if row.credential_name not in credentials:
                        errors.append(f"Row {row.row_num}: Credential '{row.credential_name}' not found")
                        continue

                    name_match = by_name.get(row.name)
                    ip_match = by_ip.get(row.ip)
                    if name_match and ip_match and name_match.id != ip_match.id:
                        errors.append(f"Row {row.row_num}: Name '{row.name}' and IP '{row.ip}' match different switches")
                        continue
                    if name_match or ip_match:
                        duplicate_count += 1

                duplicate_mode = "skip"
                if duplicate_count:
                    duplicate_mode = self._ask_duplicate_mode(duplicate_count, "switch(es)")

                for row in parse_result.rows:
                    credential_id = credentials.get(row.credential_name)
                    if not credential_id:
                        skipped += 1
                        continue

                    existing_by_name = by_name.get(row.name)
                    existing_by_ip = by_ip.get(row.ip)
                    if existing_by_name and existing_by_ip and existing_by_name.id != existing_by_ip.id:
                        skipped += 1
                        continue

                    existing = existing_by_name or existing_by_ip
                    if existing:
                        if duplicate_mode == "skip":
                            skipped += 1
                            self._write_console(f"Skipped duplicate switch: {row.name} ({row.ip})")
                            continue
                        repo.update_switch(
                            existing.id,
                            name=row.name,
                            ip=row.ip,
                            protocol=row.protocol,
                            port=row.port,
                            credential_id=credential_id,
                            notes=row.notes,
                        )
                        updated += 1
                        self._write_console(f"Updated switch: {row.name} ({row.ip})")
                    else:
                        switch = repo.create_switch(
                            name=row.name,
                            ip=row.ip,
                            protocol=row.protocol,
                            port=row.port,
                            credential_id=credential_id,
                            notes=row.notes,
                        )
                        by_name[switch.name] = switch
                        by_ip[switch.ip] = switch
                        created += 1
                        self._write_console(f"Imported switch: {row.name} ({row.ip})")

            failed = len(errors)
            message = self._format_bulk_result(
                f"Import completed from {source_name}.",
                created=created,
                updated=updated,
                skipped=skipped,
                failed=failed,
                errors=errors,
            )
            if created or updated:
                Messagebox.show_info(message, "Import Complete")
            else:
                Messagebox.show_warning(message, "Import Complete")
            self._load_data()
        except Exception as e:
            Messagebox.show_error(f"Failed to import switches: {e}", "Import Error")
            logger.exception("Bulk switch import failed")
```

- [ ] **Step 4: Replace `_batch_import` with shared parser**

Replace the body of `_batch_import` with:

```python
    def _batch_import(self):
        """Batch import switches from CSV file"""
        from tkinter import filedialog

        filename = filedialog.askopenfilename(
            title="Select CSV File to Import Switches",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return

        instructions = (
            "CSV Format Expected:\n\n"
            "name,ip,protocol,port,credential_name,notes\n\n"
            "Example:\n"
            "Switch01,192.168.1.1,ssh,22,admin_cred,Main switch\n"
            "Switch02,192.168.1.2,telnet,23,user_cred,Backup switch\n\n"
            "credential_name must match an existing credential."
        )
        if not Messagebox.show_question(instructions + "\n\nContinue with import?", "CSV Import Format"):
            return

        try:
            with open(filename, 'r', encoding='utf-8') as csvfile:
                self._import_switch_bulk_text(csvfile.read(), filename)
        except Exception as e:
            Messagebox.show_error(f"Failed to read CSV: {e}", "Import Error")
            logger.exception("CSV import failed")
```

- [ ] **Step 5: Add paste import dialog**

Add this method inside `class InventoryView`, after `_batch_import`:

```python
    def _paste_bulk_import(self):
        """Import switches from pasted CSV text"""
        dialog = ttk.Toplevel(self.frame)
        dialog.title("Paste Switches")
        dialog.geometry("850x500")
        dialog.transient(self.frame)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill=BOTH, expand=YES)

        ttk.Label(
            frame,
            text="Paste rows as: name,ip,protocol,port,credential_name,notes",
            font=("Segoe UI", 10)
        ).pack(anchor=W, pady=(0, 8))

        text = ttk.Text(frame, height=18, wrap=NONE, font=("Consolas", 10))
        text.pack(fill=BOTH, expand=YES)
        text.insert("1.0", "name,ip,protocol,port,credential_name,notes\nSwitch01,192.168.1.1,ssh,22,admin_cred,Main switch")

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=X, pady=(10, 0))

        def import_pasted():
            value = text.get("1.0", END).strip()
            if not value:
                Messagebox.show_warning("Paste at least one row", "No Data")
                return
            dialog.destroy()
            self._import_switch_bulk_text(value, "pasted text")

        ttk.Button(button_frame, text="Import", command=import_pasted, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy, bootstyle=SECONDARY).pack(side=LEFT, padx=5)
```

- [ ] **Step 6: Replace `_delete_switch` with multi-delete**

Replace `_delete_switch` with:

```python
    def _delete_switch(self):
        """Delete selected switches"""
        rows = self._get_selected_switch_rows()
        if not rows:
            Messagebox.show_warning("Please select one or more switches to delete", "No Selection")
            return

        names = [row['name'] for row in rows]
        message = (
            f"Delete {len(rows)} switch(es) and all related backups?\n\n"
            f"{self._format_name_preview(names)}"
        )
        if not Messagebox.show_question(message, "Confirm Delete"):
            return

        deleted = 0
        errors = []
        for row in rows:
            try:
                with Repository() as repo:
                    if repo.delete_switch(row['id']):
                        deleted += 1
                        self._write_console(f"Deleted switch: {row['name']}")
                    else:
                        errors.append(f"Switch not found: {row['name']}")
            except Exception as e:
                errors.append(f"{row['name']}: {e}")

        message = self._format_bulk_result(
            "Switch delete completed.",
            created=0,
            updated=deleted,
            skipped=0,
            failed=len(errors),
            errors=errors,
        ).replace("Updated", "Deleted")
        if errors:
            Messagebox.show_warning(message, "Delete Complete")
        else:
            Messagebox.show_info(message, "Delete Complete")
        self._load_data()
```

- [ ] **Step 7: Extract backup start helper and update `_get_data`**

Add this method inside `class InventoryView`, before `_get_data`:

```python
    def _start_backup_for_switch(self, switch_id, switch_name, switch_ip, switch_protocol, switch_port):
        if switch_id in self.active_backups:
            self._write_console(f"Skipped active backup: {switch_name}")
            return False

        self.active_backups.add(switch_id)

        def worker():
            try:
                self.queue.put(('console', "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
                self.queue.put(('console', f"[{len(self.active_backups)} active] Starting backup for: {switch_name}"))
                self.queue.put(('console', f"Target: {switch_protocol}://{switch_ip}:{switch_port}"))
                self.queue.put(('console', f"Connecting via {switch_protocol}..."))

                logger.info(f"[PARALLEL BACKUP] Starting backup for {switch_name} ({len(self.active_backups)} active)")
                result = self.backup_service.execute_backup(switch_id, backup_type='manual')

                if result['success']:
                    self.queue.put(('console', f"✓ Backup completed successfully for {switch_name}"))
                    self.queue.put(('console', f"  - Size: {result['size_kb']:.1f} KB"))
                    self.queue.put(('console', f"  - File: {result['file_path']}"))
                    self.queue.put(('success', switch_name, switch_id))
                else:
                    self.queue.put(('console', f"✗ Backup failed for {switch_name}: {result['message']}"))
                    self.queue.put(('error', switch_name, result['message'], switch_id))
            except Exception as e:
                self.queue.put(('console', f"✗ Error for {switch_name}: {str(e)}"))
                self.queue.put(('error', switch_name, str(e), switch_id))
            finally:
                self.queue.put(('cleanup', switch_id))

        thread = threading.Thread(target=worker, daemon=True, name=f"Backup-{switch_name}")
        thread.start()
        return True
```

Replace `_get_data` with:

```python
    def _get_data(self):
        """Execute backup for selected switches"""
        rows = self._get_selected_switch_rows()
        if not rows:
            Messagebox.show_warning("Please select one or more switches", "No Selection")
            return

        started = 0
        skipped = 0
        for row in rows:
            if self._start_backup_for_switch(
                row['id'], row['name'], row['ip'], row['protocol'], row['port']
            ):
                started += 1
            else:
                skipped += 1

        self._write_console(f"Bulk backup requested: started={started}, skipped={skipped}")
        if skipped:
            Messagebox.show_info(
                f"Started {started} backup(s). Skipped {skipped} active backup(s).",
                "Backups Started"
            )
        logger.info(f"Bulk backup request complete - started={started}, skipped={skipped}")
```

- [ ] **Step 8: Run syntax and unit verification**

Run:

```powershell
rtk python -m py_compile app/main.py
rtk python -m unittest discover app/tests/
```

Expected: both commands pass.

- [ ] **Step 9: Manual inventory smoke test**

Run app:

```powershell
rtk python -m app.main
```

Manual checks:
- Inventory table allows selecting multiple rows with Ctrl/Shift.
- `Batch Import` imports valid CSV and reports duplicates.
- `Paste Bulk` imports pasted rows and reports duplicates.
- Multi-delete asks once and deletes selected rows.
- Multi-Get Data starts backups for selected rows and skips active backups.

- [ ] **Step 10: Checkpoint**

Run:

```powershell
rtk git diff -- app/ui/inventory_view.py app/tests/test_bulk_operations.py
```

Expected: inventory UI and parser changes shown. Do not commit unless user explicitly approved commits.

---

### Task 4: Add schedule bulk parser tests

**Files:**
- Modify: `app/tests/test_bulk_operations.py`
- Modify later: `app/ui/schedules_view.py`

- [ ] **Step 1: Extend test imports**

In `app/tests/test_bulk_operations.py`, change the imports to:

```python
from app.ui.inventory_view import parse_switch_bulk_text
from app.ui.schedules_view import parse_schedule_bulk_text
```

- [ ] **Step 2: Add failing schedule parser tests**

Add this class before the `if __name__ == "__main__"` block:

```python
class TestScheduleBulkParsing(unittest.TestCase):
    def test_parse_schedule_csv_with_header(self):
        text = "switch_name,schedule_type,interval_minutes,hour,minute,enabled\nSW1,interval,60,8,30,true\n"

        result = parse_schedule_bulk_text(text)

        self.assertEqual([], result.errors)
        self.assertEqual(1, len(result.rows))
        row = result.rows[0]
        self.assertEqual(2, row.row_num)
        self.assertEqual("SW1", row.switch_name)
        self.assertEqual("interval", row.schedule_type)
        self.assertEqual(60, row.interval_minutes)
        self.assertEqual(8, row.schedule_hour)
        self.assertEqual(30, row.schedule_minute)
        self.assertTrue(row.enabled)

    def test_parse_schedule_csv_without_header_daily_defaults_enabled(self):
        text = "SW2,daily,,9,15,\n"

        result = parse_schedule_bulk_text(text)

        self.assertEqual([], result.errors)
        self.assertEqual(1, len(result.rows))
        row = result.rows[0]
        self.assertEqual(1, row.row_num)
        self.assertEqual("SW2", row.switch_name)
        self.assertEqual("daily", row.schedule_type)
        self.assertEqual(1440, row.interval_minutes)
        self.assertEqual(9, row.schedule_hour)
        self.assertEqual(15, row.schedule_minute)
        self.assertTrue(row.enabled)

    def test_parse_schedule_csv_reports_invalid_rows(self):
        text = "switch_name,schedule_type,interval_minutes,hour,minute,enabled\n,interval,60,8,0,true\nSW3,bad,60,8,0,true\nSW4,interval,,8,0,true\nSW5,interval,0,8,0,true\nSW6,daily,,24,0,true\nSW7,daily,,8,60,true\nSW8,daily,,8,0,maybe\n"

        result = parse_schedule_bulk_text(text)

        self.assertEqual([], result.rows)
        self.assertEqual(7, len(result.errors))
        self.assertIn("Row 2: Missing switch name", result.errors)
        self.assertIn("Row 3: Invalid schedule type 'bad'", result.errors)
        self.assertIn("Row 4: interval_minutes is required for interval schedules", result.errors)
        self.assertIn("Row 5: interval_minutes must be between 1 and 43200", result.errors)
        self.assertIn("Row 6: hour must be between 0 and 23", result.errors)
        self.assertIn("Row 7: minute must be between 0 and 59", result.errors)
        self.assertIn("Row 8: enabled must be true or false", result.errors)
```

- [ ] **Step 3: Run schedule parser tests to verify RED**

Run:

```powershell
rtk python -m unittest app.tests.test_bulk_operations.TestScheduleBulkParsing
```

Expected: FAIL with import error like `cannot import name 'parse_schedule_bulk_text'`.

- [ ] **Step 4: Checkpoint**

Run:

```powershell
rtk git diff -- app/tests/test_bulk_operations.py
```

Expected: schedule parser tests shown. Do not commit unless user explicitly approved commits.

---

### Task 5: Implement schedule bulk parser

**Files:**
- Modify: `app/ui/schedules_view.py`
- Test: `app/tests/test_bulk_operations.py`

- [ ] **Step 1: Add imports and parser dataclasses**

In `app/ui/schedules_view.py`, update imports near the top:

```python
"""Schedules management view"""
import logging
import csv
import io
from dataclasses import dataclass
from tkinter import END
from datetime import datetime, timedelta
from typing import List
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
```

Add this code after `logger = logging.getLogger(__name__)`:

```python
SCHEDULE_BULK_COLUMNS = ("switch_name", "schedule_type", "interval_minutes", "hour", "minute", "enabled")
VALID_SCHEDULE_TYPES = {"interval", "daily", "weekly", "monthly"}
SCHEDULE_TYPE_INTERVALS = {
    "daily": 1440,
    "weekly": 10080,
    "monthly": 43200,
}


@dataclass
class ScheduleBulkRow:
    row_num: int
    switch_name: str
    schedule_type: str
    interval_minutes: int
    schedule_hour: int
    schedule_minute: int
    enabled: bool


@dataclass
class ScheduleBulkParseResult:
    rows: List[ScheduleBulkRow]
    errors: List[str]


def _is_schedule_header(values: List[str]) -> bool:
    normalized = {value.strip().lower() for value in values}
    return "switch_name" in normalized and "schedule_type" in normalized


def _schedule_record_from_values(values: List[str]) -> dict:
    return {
        column: values[index].strip() if index < len(values) else ""
        for index, column in enumerate(SCHEDULE_BULK_COLUMNS)
    }


def _parse_schedule_enabled(value: str):
    normalized = value.strip().lower()
    if normalized == "":
        return True
    if normalized in {"true", "yes", "1", "enabled", "enable"}:
        return True
    if normalized in {"false", "no", "0", "disabled", "disable"}:
        return False
    return None


def parse_schedule_bulk_text(text: str) -> ScheduleBulkParseResult:
    csv_rows = [
        row for row in csv.reader(io.StringIO(text))
        if any(cell.strip() for cell in row)
    ]
    if not csv_rows:
        return ScheduleBulkParseResult(rows=[], errors=["No rows found"])

    has_header = _is_schedule_header(csv_rows[0])
    header = [cell.strip().lower() for cell in csv_rows[0]] if has_header else []
    data_rows = csv_rows[1:] if has_header else csv_rows
    first_row_num = 2 if has_header else 1

    parsed_rows = []
    errors = []

    for offset, values in enumerate(data_rows):
        row_num = first_row_num + offset
        if has_header:
            record = {
                header[index]: values[index].strip() if index < len(values) else ""
                for index in range(len(header))
            }
        else:
            record = _schedule_record_from_values(values)

        switch_name = record.get("switch_name", "").strip()
        schedule_type = record.get("schedule_type", "interval").strip().lower() or "interval"
        interval_text = record.get("interval_minutes", "").strip()
        hour_text = record.get("hour", "8").strip() or "8"
        minute_text = record.get("minute", "0").strip() or "0"
        enabled_value = _parse_schedule_enabled(record.get("enabled", ""))

        if not switch_name:
            errors.append(f"Row {row_num}: Missing switch name")
            continue
        if schedule_type not in VALID_SCHEDULE_TYPES:
            errors.append(f"Row {row_num}: Invalid schedule type '{schedule_type}'")
            continue

        if schedule_type == "interval":
            if not interval_text:
                errors.append(f"Row {row_num}: interval_minutes is required for interval schedules")
                continue
            try:
                interval_minutes = int(interval_text)
            except ValueError:
                errors.append(f"Row {row_num}: interval_minutes must be between 1 and 43200")
                continue
            if not 1 <= interval_minutes <= 43200:
                errors.append(f"Row {row_num}: interval_minutes must be between 1 and 43200")
                continue
        else:
            interval_minutes = SCHEDULE_TYPE_INTERVALS[schedule_type]

        try:
            schedule_hour = int(hour_text)
        except ValueError:
            errors.append(f"Row {row_num}: hour must be between 0 and 23")
            continue
        if not 0 <= schedule_hour <= 23:
            errors.append(f"Row {row_num}: hour must be between 0 and 23")
            continue

        try:
            schedule_minute = int(minute_text)
        except ValueError:
            errors.append(f"Row {row_num}: minute must be between 0 and 59")
            continue
        if not 0 <= schedule_minute <= 59:
            errors.append(f"Row {row_num}: minute must be between 0 and 59")
            continue

        if enabled_value is None:
            errors.append(f"Row {row_num}: enabled must be true or false")
            continue

        parsed_rows.append(ScheduleBulkRow(
            row_num=row_num,
            switch_name=switch_name,
            schedule_type=schedule_type,
            interval_minutes=interval_minutes,
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
            enabled=enabled_value,
        ))

    return ScheduleBulkParseResult(rows=parsed_rows, errors=errors)
```

- [ ] **Step 2: Run schedule parser tests to verify GREEN**

Run:

```powershell
rtk python -m unittest app.tests.test_bulk_operations.TestScheduleBulkParsing
```

Expected: PASS.

- [ ] **Step 3: Run all tests**

Run:

```powershell
rtk python -m unittest discover app/tests/
```

Expected: PASS.

- [ ] **Step 4: Checkpoint**

Run:

```powershell
rtk git diff -- app/ui/schedules_view.py app/tests/test_bulk_operations.py
```

Expected: schedule parser helpers and tests shown. Do not commit unless user explicitly approved commits.

---

### Task 6: Add bulk schedule dialog and CSV import

**Files:**
- Modify: `app/ui/schedules_view.py`
- Test: manual UI smoke plus existing unittest suite

- [ ] **Step 1: Enable multi-select and add toolbar buttons**

In `SchedulesView._create_ui`, after the `Add Schedule` button block, add:

```python
ttk.Button(
    toolbar,
    text="➕ Bulk Add",
    command=self._bulk_add_schedule,
    bootstyle=SUCCESS
).pack(side=LEFT, padx=5)

ttk.Button(
    toolbar,
    text="📋 Import CSV",
    command=self._import_schedules_csv,
    bootstyle=SUCCESS
).pack(side=LEFT, padx=5)
```

Change schedule tree creation to:

```python
self.tree = ttk.Treeview(
    self.frame,
    columns=columns,
    show="headings",
    height=20,
    selectmode="extended"
)
```

- [ ] **Step 2: Add shared schedule UI helpers inside `SchedulesView`**

Add these methods inside `class SchedulesView`, before `_add_schedule`:

```python
    def _get_selected_job_rows(self):
        rows = []
        for item in self.tree.selection():
            values = self.tree.item(item)['values']
            rows.append({
                'id': int(values[0]),
                'switch_name': values[1],
            })
        return rows

    def _format_name_preview(self, names):
        preview = ", ".join(names[:8])
        if len(names) > 8:
            preview += f", ... and {len(names) - 8} more"
        return preview

    def _format_bulk_result(self, title, created=0, updated=0, skipped=0, failed=0, errors=None):
        errors = errors or []
        message = (
            f"{title}\n\n"
            f"Created: {created}\n"
            f"Updated: {updated}\n"
            f"Skipped: {skipped}\n"
            f"Failed: {failed}"
        )
        if errors:
            message += "\n\nErrors:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                message += f"\n... and {len(errors) - 10} more errors"
        return message

    def _ask_duplicate_mode(self, duplicate_count, item_label):
        result = Messagebox.yesno(
            f"Found {duplicate_count} duplicate {item_label}.\n\n"
            "Choose Yes to update existing records.\n"
            "Choose No to skip duplicates.",
            "Duplicates Found"
        )
        return "update" if result == "Yes" else "skip"

    def _find_duplicate_job(self, jobs, switch_id, interval_minutes, schedule_hour, schedule_minute):
        for job in jobs:
            if (
                job.switch_id == switch_id
                and job.interval_minutes == interval_minutes
                and getattr(job, 'schedule_hour', 8) == schedule_hour
                and getattr(job, 'schedule_minute', 0) == schedule_minute
            ):
                return job
        return None
```

- [ ] **Step 3: Add bulk add action**

Add this method inside `class SchedulesView`, after `_add_schedule`:

```python
    def _bulk_add_schedule(self):
        """Add one schedule configuration to multiple switches"""
        ScheduleDialog(self.frame, self.schedule_service, callback=self._load_data, bulk=True)
```

- [ ] **Step 4: Extend `ScheduleDialog.__init__` for bulk mode**

Change the signature and assignments:

```python
    def __init__(self, parent, schedule_service, job_id=None, callback=None, bulk=False):
        self.schedule_service = schedule_service
        self.job_id = job_id
        self.callback = callback
        self.bulk = bulk

        self.dialog = ttk.Toplevel(parent)
        if job_id:
            self.dialog.title("Edit Schedule")
        elif bulk:
            self.dialog.title("Bulk Add Schedules")
        else:
            self.dialog.title("Add Schedule")
        self.dialog.geometry("650x520" if bulk else "500x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()
```

- [ ] **Step 5: Replace switch selector block in `ScheduleDialog._create_ui`**

Replace the current switch selector block (`# Switch` through initial combobox selection) with:

```python
        ttk.Label(frame, text="Switch:" if not self.bulk else "Switches:").grid(row=0, column=0, sticky=NW, pady=5)
        self.switch_var = ttk.StringVar()

        with Repository() as repo:
            switches = repo.list_switches()
            switch_names = [s.name for s in switches]

        if self.bulk:
            selector_frame = ttk.Frame(frame)
            selector_frame.grid(row=0, column=1, columnspan=2, sticky=NSEW, pady=5)
            self.switch_list = ttk.Treeview(
                selector_frame,
                columns=("Switch",),
                show="headings",
                height=8,
                selectmode="extended"
            )
            self.switch_list.heading("Switch", text="Switch")
            self.switch_list.column("Switch", width=300)
            for name in switch_names:
                self.switch_list.insert("", END, values=(name,))
            self.switch_list.pack(side=LEFT, fill=BOTH, expand=YES)
            switch_scrollbar = ttk.Scrollbar(selector_frame, orient=VERTICAL, command=self.switch_list.yview)
            self.switch_list.configure(yscrollcommand=switch_scrollbar.set)
            switch_scrollbar.pack(side=RIGHT, fill=Y)

            switch_button_frame = ttk.Frame(frame)
            switch_button_frame.grid(row=1, column=1, columnspan=2, sticky=W, pady=(0, 5))
            ttk.Button(
                switch_button_frame,
                text="Select All",
                command=lambda: self.switch_list.selection_set(self.switch_list.get_children()),
                bootstyle=SECONDARY,
            ).pack(side=LEFT, padx=5)
            ttk.Button(
                switch_button_frame,
                text="Clear",
                command=lambda: self.switch_list.selection_remove(self.switch_list.selection()),
                bootstyle=SECONDARY,
            ).pack(side=LEFT, padx=5)
            schedule_start_row = 2
        else:
            self.switch_combo = ttk.Combobox(frame, textvariable=self.switch_var, values=switch_names, state="readonly", width=35)
            self.switch_combo.grid(row=0, column=1, columnspan=2, pady=5, sticky=W)
            if switch_names:
                self.switch_combo.current(0)
            schedule_start_row = 1
```

Then change every schedule option row below this block to use `schedule_start_row` offsets:

```python
        ttk.Label(frame, text="Schedule Type:").grid(row=schedule_start_row, column=0, sticky=W, pady=10)
        type_frame.grid(row=schedule_start_row, column=1, columnspan=2, sticky=W, pady=10)
        self.interval_frame.grid(row=schedule_start_row + 1, column=0, columnspan=3, sticky=EW, pady=10)
        self.daily_frame.grid(row=schedule_start_row + 1, column=0, columnspan=3, sticky=EW, pady=10)
        self.weekly_frame.grid(row=schedule_start_row + 1, column=0, columnspan=3, sticky=EW, pady=10)
        self.monthly_frame.grid(row=schedule_start_row + 1, column=0, columnspan=3, sticky=EW, pady=10)
        btn_frame.grid(row=schedule_start_row + 2, column=0, columnspan=3, pady=20)
```

- [ ] **Step 6: Add selected switch and duplicate helpers in `ScheduleDialog`**

Add these methods inside `class ScheduleDialog`, before `_save`:

```python
    def _get_selected_switch_names(self):
        if not self.bulk:
            return [self.switch_var.get()] if self.switch_var.get() else []
        names = []
        for item in self.switch_list.selection():
            values = self.switch_list.item(item)['values']
            if values:
                names.append(values[0])
        return names

    def _find_duplicate_job(self, jobs, switch_id, interval_minutes, schedule_hour, schedule_minute):
        for job in jobs:
            if (
                job.switch_id == switch_id
                and job.interval_minutes == interval_minutes
                and getattr(job, 'schedule_hour', 8) == schedule_hour
                and getattr(job, 'schedule_minute', 0) == schedule_minute
            ):
                return job
        return None
```

- [ ] **Step 7: Replace switch-name validation in `_save`**

At the top of `_save`, replace:

```python
        switch_name = self.switch_var.get()

        if not switch_name:
            Messagebox.show_error("Please select a switch", "Validation Error")
            return
```

with:

```python
        switch_names = self._get_selected_switch_names()

        if not switch_names:
            Messagebox.show_error("Please select one or more switches", "Validation Error")
            return
```

- [ ] **Step 8: Replace save persistence block for bulk support**

In `_save`, replace the `try:` block that starts with `# First, create or update the job` and ends before `# Show summary` with:

```python
        try:
            jobs_to_schedule = []
            created = 0
            updated = 0
            skipped = 0
            errors = []

            with Repository() as repo:
                all_jobs = repo.list_jobs()
                switches = {switch.name: switch for switch in repo.list_switches()}

                if self.job_id:
                    switch = switches.get(switch_names[0])
                    if not switch:
                        Messagebox.show_error("Switch not found", "Error")
                        return
                    repo.update_job(self.job_id, interval_minutes=interval, schedule_hour=schedule_hour, schedule_minute=schedule_minute)
                    job_id = self.job_id
                    switch_id = switch.id
                    jobs_to_schedule.append((job_id, switch_id, interval, schedule_hour, schedule_minute, True))
                    updated = 1
                else:
                    duplicate_rows = []
                    for switch_name in switch_names:
                        switch = switches.get(switch_name)
                        if not switch:
                            errors.append(f"Switch not found: {switch_name}")
                            continue
                        duplicate = self._find_duplicate_job(
                            all_jobs,
                            switch.id,
                            interval,
                            schedule_hour,
                            schedule_minute,
                        )
                        if duplicate:
                            duplicate_rows.append((switch, duplicate))

                    duplicate_mode = "skip"
                    if duplicate_rows:
                        result = Messagebox.yesno(
                            f"Found {len(duplicate_rows)} duplicate schedule(s).\n\n"
                            "Choose Yes to update existing records.\n"
                            "Choose No to skip duplicates.",
                            "Duplicates Found"
                        )
                        duplicate_mode = "update" if result == "Yes" else "skip"

                    duplicate_by_switch = {switch.id: duplicate for switch, duplicate in duplicate_rows}
                    for switch_name in switch_names:
                        switch = switches.get(switch_name)
                        if not switch:
                            skipped += 1
                            continue
                        duplicate = duplicate_by_switch.get(switch.id)
                        if duplicate:
                            if duplicate_mode == "skip":
                                skipped += 1
                                continue
                            repo.update_job(
                                duplicate.id,
                                interval_minutes=interval,
                                enabled=True,
                                schedule_hour=schedule_hour,
                                schedule_minute=schedule_minute,
                            )
                            jobs_to_schedule.append((duplicate.id, switch.id, interval, schedule_hour, schedule_minute, True))
                            updated += 1
                        else:
                            job = repo.create_job(switch.id, interval, enabled=True)
                            job.schedule_hour = schedule_hour
                            job.schedule_minute = schedule_minute
                            jobs_to_schedule.append((job.id, switch.id, interval, schedule_hour, schedule_minute, True))
                            created += 1

            for job_id, switch_id, interval_minutes, job_hour, job_minute, enabled in jobs_to_schedule:
                if self.job_id:
                    self.schedule_service.remove_job(job_id)
                if enabled:
                    self.schedule_service.add_job(job_id, switch_id, interval_minutes, job_hour, job_minute)
```

- [ ] **Step 9: Replace success message block**

Replace the existing `Messagebox.show_info(...)` block in `_save` with:

```python
            if self.bulk:
                Messagebox.show_info(
                    f"Bulk schedule save complete.\n\nCreated: {created}\nUpdated: {updated}\nSkipped: {skipped}\nFailed: {len(errors)}",
                    "Success"
                )
            else:
                Messagebox.show_info(
                    f"Schedule saved successfully!\n\n{type_desc.get(schedule_type, 'Schedule configured')}\n\nNext run time will update shortly.",
                    "Success"
                )
```

- [ ] **Step 10: Add schedule CSV import methods inside `SchedulesView`**

Add these methods inside `class SchedulesView`, after `_bulk_add_schedule`:

```python
    def _import_schedules_csv(self):
        """Import schedules from CSV file"""
        from tkinter import filedialog

        filename = filedialog.askopenfilename(
            title="Select CSV File to Import Schedules",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return

        instructions = (
            "CSV Format Expected:\n\n"
            "switch_name,schedule_type,interval_minutes,hour,minute,enabled\n\n"
            "Examples:\n"
            "Switch01,interval,60,8,0,true\n"
            "Switch02,daily,,9,30,true\n\n"
            "switch_name must match an existing switch."
        )
        if not Messagebox.show_question(instructions + "\n\nContinue with import?", "Schedule CSV Import Format"):
            return

        try:
            with open(filename, 'r', encoding='utf-8') as csvfile:
                self._import_schedule_bulk_text(csvfile.read(), filename)
        except Exception as e:
            Messagebox.show_error(f"Failed to read CSV: {e}", "Import Error")
            logger.exception("Schedule CSV import failed")

    def _import_schedule_bulk_text(self, text, source_name):
        parse_result = parse_schedule_bulk_text(text)
        errors = list(parse_result.errors)
        if not parse_result.rows:
            Messagebox.show_warning(
                self._format_bulk_result(f"No schedules imported from {source_name}.", failed=len(errors), errors=errors),
                "Import Complete"
            )
            return

        created = 0
        updated = 0
        skipped = 0
        jobs_to_schedule = []

        try:
            with Repository() as repo:
                switches = {switch.name: switch for switch in repo.list_switches()}
                jobs = repo.list_jobs()
                duplicate_count = 0

                for row in parse_result.rows:
                    switch = switches.get(row.switch_name)
                    if not switch:
                        errors.append(f"Row {row.row_num}: Switch '{row.switch_name}' not found")
                        continue
                    if self._find_duplicate_job(jobs, switch.id, row.interval_minutes, row.schedule_hour, row.schedule_minute):
                        duplicate_count += 1

                duplicate_mode = "skip"
                if duplicate_count:
                    duplicate_mode = self._ask_duplicate_mode(duplicate_count, "schedule(s)")

                for row in parse_result.rows:
                    switch = switches.get(row.switch_name)
                    if not switch:
                        skipped += 1
                        continue
                    duplicate = self._find_duplicate_job(jobs, switch.id, row.interval_minutes, row.schedule_hour, row.schedule_minute)
                    if duplicate:
                        if duplicate_mode == "skip":
                            skipped += 1
                            continue
                        repo.update_job(
                            duplicate.id,
                            interval_minutes=row.interval_minutes,
                            enabled=row.enabled,
                            schedule_hour=row.schedule_hour,
                            schedule_minute=row.schedule_minute,
                        )
                        jobs_to_schedule.append((duplicate.id, switch.id, row.interval_minutes, row.schedule_hour, row.schedule_minute, row.enabled))
                        updated += 1
                    else:
                        job = repo.create_job(switch.id, row.interval_minutes, enabled=row.enabled)
                        job.schedule_hour = row.schedule_hour
                        job.schedule_minute = row.schedule_minute
                        jobs.append(job)
                        jobs_to_schedule.append((job.id, switch.id, row.interval_minutes, row.schedule_hour, row.schedule_minute, row.enabled))
                        created += 1

            for job_id, switch_id, interval_minutes, schedule_hour, schedule_minute, enabled in jobs_to_schedule:
                if enabled:
                    self.schedule_service.add_job(job_id, switch_id, interval_minutes, schedule_hour, schedule_minute)
                elif job_id in self.schedule_service.job_map:
                    self.schedule_service.remove_job(job_id)

            message = self._format_bulk_result(
                f"Schedule import completed from {source_name}.",
                created=created,
                updated=updated,
                skipped=skipped,
                failed=len(errors),
                errors=errors,
            )
            if created or updated:
                Messagebox.show_info(message, "Import Complete")
            else:
                Messagebox.show_warning(message, "Import Complete")
            self._load_data()
        except Exception as e:
            Messagebox.show_error(f"Failed to import schedules: {e}", "Import Error")
            logger.exception("Bulk schedule import failed")
```

- [ ] **Step 11: Run syntax and unit verification**

Run:

```powershell
rtk python -m py_compile app/main.py
rtk python -m unittest discover app/tests/
```

Expected: both commands pass.

- [ ] **Step 12: Manual schedule import smoke test**

Run app:

```powershell
rtk python -m app.main
```

Manual checks:
- Schedules table allows selecting multiple rows.
- `Bulk Add` opens multi-switch selector.
- Selecting multiple switches and saving creates schedules.
- `Import CSV` imports valid schedule rows.
- Duplicate prompt appears when CSV or bulk add repeats a schedule.

- [ ] **Step 13: Checkpoint**

Run:

```powershell
rtk git diff -- app/ui/schedules_view.py app/tests/test_bulk_operations.py
```

Expected: schedule UI/import changes shown. Do not commit unless user explicitly approved commits.

---

### Task 7: Extend schedule delete, enable, disable, and start-now to selected rows

**Files:**
- Modify: `app/ui/schedules_view.py`
- Test: manual UI smoke plus existing unittest suite

- [ ] **Step 1: Replace `_delete_schedule` with multi-delete**

Replace `_delete_schedule` with:

```python
    def _delete_schedule(self):
        """Delete selected schedules"""
        rows = self._get_selected_job_rows()
        if not rows:
            Messagebox.show_warning("Please select one or more schedules to delete", "No Selection")
            return

        names = [row['switch_name'] for row in rows]
        message = (
            f"Delete {len(rows)} schedule(s)?\n\n"
            f"{self._format_name_preview(names)}"
        )
        if not Messagebox.show_question(message, "Confirm Delete"):
            return

        deleted = 0
        errors = []
        for row in rows:
            try:
                if row['id'] in self.schedule_service.job_map:
                    self.schedule_service.remove_job(row['id'])
                with Repository() as repo:
                    if repo.delete_job(row['id']):
                        deleted += 1
                    else:
                        errors.append(f"Schedule not found for {row['switch_name']}")
            except Exception as e:
                errors.append(f"{row['switch_name']}: {e}")

        message = self._format_bulk_result(
            "Schedule delete completed.",
            updated=deleted,
            failed=len(errors),
            errors=errors,
        ).replace("Updated", "Deleted")
        if errors:
            Messagebox.show_warning(message, "Delete Complete")
        else:
            Messagebox.show_info(message, "Delete Complete")
        self._load_data()
```

- [ ] **Step 2: Replace `_enable_schedule` with multi-enable**

Replace `_enable_schedule` with:

```python
    def _enable_schedule(self):
        """Enable selected schedules"""
        rows = self._get_selected_job_rows()
        if not rows:
            Messagebox.show_warning("Please select one or more schedules", "No Selection")
            return

        enabled = 0
        errors = []
        jobs_to_schedule = []

        for row in rows:
            try:
                with Repository() as repo:
                    job = repo.get_job(row['id'])
                    if not job:
                        errors.append(f"Schedule not found for {row['switch_name']}")
                        continue
                    schedule_hour = getattr(job, 'schedule_hour', 8)
                    schedule_minute = getattr(job, 'schedule_minute', 0)
                    switch_id = job.switch_id
                    interval_minutes = job.interval_minutes
                    repo.update_job(row['id'], enabled=True)
                    jobs_to_schedule.append((row['id'], switch_id, interval_minutes, schedule_hour, schedule_minute))
                    enabled += 1
            except Exception as e:
                errors.append(f"{row['switch_name']}: {e}")

        for job_id, switch_id, interval_minutes, schedule_hour, schedule_minute in jobs_to_schedule:
            try:
                if job_id in self.schedule_service.job_map:
                    self.schedule_service.resume_job(job_id)
                else:
                    self.schedule_service.add_job(job_id, switch_id, interval_minutes, schedule_hour, schedule_minute)
            except Exception as e:
                errors.append(f"Job {job_id}: {e}")

        message = self._format_bulk_result(
            "Schedule enable completed.",
            updated=enabled,
            failed=len(errors),
            errors=errors,
        ).replace("Updated", "Enabled")
        if errors:
            Messagebox.show_warning(message, "Enable Complete")
        else:
            Messagebox.show_info(message, "Enable Complete")
        self._load_data()
```

- [ ] **Step 3: Replace `_disable_schedule` with multi-disable**

Replace `_disable_schedule` with:

```python
    def _disable_schedule(self):
        """Disable selected schedules"""
        rows = self._get_selected_job_rows()
        if not rows:
            Messagebox.show_warning("Please select one or more schedules", "No Selection")
            return

        disabled = 0
        errors = []
        for row in rows:
            try:
                with Repository() as repo:
                    if repo.update_job(row['id'], enabled=False):
                        disabled += 1
                    else:
                        errors.append(f"Schedule not found for {row['switch_name']}")
                        continue
                if row['id'] in self.schedule_service.job_map:
                    self.schedule_service.pause_job(row['id'])
            except Exception as e:
                errors.append(f"{row['switch_name']}: {e}")

        message = self._format_bulk_result(
            "Schedule disable completed.",
            updated=disabled,
            failed=len(errors),
            errors=errors,
        ).replace("Updated", "Disabled")
        if errors:
            Messagebox.show_warning(message, "Disable Complete")
        else:
            Messagebox.show_info(message, "Disable Complete")
        self._load_data()
```

- [ ] **Step 4: Update `_start_now` to use selected helper**

In `_start_now`, replace the block that collects selected jobs:

```python
        jobs_to_run = []
        for item in selected:
            job_id = self.tree.item(item)['values'][0]
            switch_name = self.tree.item(item)['values'][1]
            jobs_to_run.append((job_id, switch_name))
```

with:

```python
        rows = self._get_selected_job_rows()
        jobs_to_run = [(row['id'], row['switch_name']) for row in rows]
```

Keep sequential background execution unchanged.

- [ ] **Step 5: Run syntax and unit verification**

Run:

```powershell
rtk python -m py_compile app/main.py
rtk python -m unittest discover app/tests/
```

Expected: both commands pass.

- [ ] **Step 6: Manual schedule operation smoke test**

Run app:

```powershell
rtk python -m app.main
```

Manual checks:
- Select multiple schedules.
- `Delete` asks once and removes all selected schedules.
- `Enable` enables all selected schedules and updates next-run data after refresh.
- `Disable` disables all selected schedules.
- `Start Now` starts selected schedules sequentially and logs progress.

- [ ] **Step 7: Checkpoint**

Run:

```powershell
rtk git diff -- app/ui/schedules_view.py
```

Expected: multi-schedule operation changes shown. Do not commit unless user explicitly approved commits.

---

### Task 8: Final verification and production build readiness

**Files:**
- Verify: `app/ui/inventory_view.py`
- Verify: `app/ui/schedules_view.py`
- Verify: `app/tests/test_bulk_operations.py`

- [ ] **Step 1: Run full unit test suite**

Run:

```powershell
rtk python -m unittest discover app/tests/
```

Expected: all tests pass.

- [ ] **Step 2: Run syntax check**

Run:

```powershell
rtk python -m py_compile app/main.py
```

Expected: exit code 0.

- [ ] **Step 3: Inspect git diff**

Run:

```powershell
rtk git diff -- app/ui/inventory_view.py app/ui/schedules_view.py app/tests/test_bulk_operations.py docs/superpowers/specs/2026-05-18-bulk-inventory-schedules-design.md docs/superpowers/plans/2026-05-18-bulk-inventory-schedules.md
```

Expected: only planned files changed for this feature, aside from pre-existing build artifacts and previous test change.

- [ ] **Step 4: Manual UI smoke test**

Run:

```powershell
rtk python -m app.main
```

Manual checklist:
- Inventory multi-select works.
- Inventory CSV bulk import works.
- Inventory paste bulk import works.
- Inventory duplicate prompt supports update or skip.
- Inventory multi-delete works.
- Inventory multi-get-data starts backups and skips active backups.
- Schedules multi-select works.
- Schedules bulk add creates schedules for multiple switches.
- Schedules CSV import works.
- Schedules duplicate prompt supports update or skip.
- Schedules multi-delete works.
- Schedules multi-enable works.
- Schedules multi-disable works.
- Schedules multi-start-now runs sequentially.

- [ ] **Step 5: Optional production build**

Only run this if the user asks for a production package after feature verification:

```powershell
rtk powershell -ExecutionPolicy Bypass -File .\build_production.ps1
```

Expected: PyInstaller executable produced. If `rtk powershell` fails on PowerShell cmdlets, rerun direct PowerShell command only after explaining the known `Get-FileHash` wrapper issue.

- [ ] **Step 6: Final status report**

Report exact commands run and exact outcomes. Include any manual UI checks that could not be performed.
