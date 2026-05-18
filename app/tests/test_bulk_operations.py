"""Tests for bulk inventory and schedule parsing helpers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.ui.inventory_view import parse_switch_bulk_text
from app.ui.schedules_view import parse_schedule_bulk_text


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


class TestScheduleBulkParsing(unittest.TestCase):
    def test_parse_schedule_csv_with_header(self):
        text = "switch_name,schedule_type,interval_minutes,hour,minute,enabled\nSW1,interval,30,1,15,false\n"

        result = parse_schedule_bulk_text(text)

        self.assertEqual([], result.errors)
        self.assertEqual(1, len(result.rows))
        row = result.rows[0]
        self.assertEqual(2, row.row_num)
        self.assertEqual("SW1", row.switch_name)
        self.assertEqual("interval", row.schedule_type)
        self.assertEqual(30, row.interval_minutes)
        self.assertEqual(1, row.schedule_hour)
        self.assertEqual(15, row.schedule_minute)
        self.assertFalse(row.enabled)

    def test_parse_schedule_csv_maps_named_schedule_types_and_defaults_enabled(self):
        text = "SW2,daily,,8,30,\nSW3,weekly,,9,45,true\nSW4,monthly,,10,0,yes\n"

        result = parse_schedule_bulk_text(text)

        self.assertEqual([], result.errors)
        self.assertEqual(3, len(result.rows))
        self.assertEqual(1440, result.rows[0].interval_minutes)
        self.assertTrue(result.rows[0].enabled)
        self.assertEqual(10080, result.rows[1].interval_minutes)
        self.assertTrue(result.rows[1].enabled)
        self.assertEqual(43200, result.rows[2].interval_minutes)
        self.assertTrue(result.rows[2].enabled)

    def test_parse_schedule_csv_reports_invalid_rows(self):
        text = "switch_name,schedule_type,interval_minutes,hour,minute,enabled\n,interval,30,8,0,true\nSW5,bad,30,8,0,true\nSW6,interval,,8,0,true\nSW7,interval,0,8,0,true\nSW8,daily,,24,0,true\nSW9,daily,,8,60,true\nSW10,daily,,8,0,maybe\n"

        result = parse_schedule_bulk_text(text)

        self.assertEqual([], result.rows)
        self.assertEqual(7, len(result.errors))
        self.assertIn("Row 2: Missing switch name", result.errors)
        self.assertIn("Row 3: Invalid schedule type 'bad'", result.errors)
        self.assertIn("Row 4: Missing interval minutes", result.errors)
        self.assertIn("Row 5: Invalid interval minutes '0'", result.errors)
        self.assertIn("Row 6: Invalid hour '24'", result.errors)
        self.assertIn("Row 7: Invalid minute '60'", result.errors)
        self.assertIn("Row 8: Invalid enabled value 'maybe'", result.errors)


if __name__ == "__main__":
    unittest.main()
