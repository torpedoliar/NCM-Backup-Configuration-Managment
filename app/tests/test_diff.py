"""Tests for diff service"""
import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.diff_service import DiffService


class TestDiffService(unittest.TestCase):
    """Test cases for DiffService"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.diff_service = DiffService()
    
    def test_unified_diff_no_changes(self):
        """Test unified diff with identical texts"""
        text1 = "line1\nline2\nline3"
        text2 = "line1\nline2\nline3"

        diff = self.diff_service.unified_diff(text1, text2)

        self.assertEqual("", diff)
    
    def test_unified_diff_line_added(self):
        """Test unified diff with added line"""
        text1 = "line1\nline2\nline3"
        text2 = "line1\nline2\nline_new\nline3"
        
        diff = self.diff_service.unified_diff(text1, text2)
        
        self.assertIn("+line_new", diff)
    
    def test_unified_diff_line_removed(self):
        """Test unified diff with removed line"""
        text1 = "line1\nline2\nline3"
        text2 = "line1\nline3"
        
        diff = self.diff_service.unified_diff(text1, text2)
        
        self.assertIn("-line2", diff)
    
    def test_unified_diff_line_modified(self):
        """Test unified diff with modified line"""
        text1 = "line1\nline2\nline3"
        text2 = "line1\nline2_modified\nline3"
        
        diff = self.diff_service.unified_diff(text1, text2)
        
        self.assertIn("-line2", diff)
        self.assertIn("+line2_modified", diff)
    
    def test_side_by_side_diff(self):
        """Test side-by-side diff generation"""
        text1 = "line1\nline2\nline3"
        text2 = "line1\nline2_modified\nline3"
        
        result = self.diff_service.side_by_side_diff(text1, text2)
        
        # Should return list of tuples
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        
        # Check tuple structure
        for item in result:
            self.assertEqual(len(item), 5)  # (linenum1, linenum2, line1, line2, opcode)
    
    def test_diff_stats_no_changes(self):
        """Test diff stats with identical texts"""
        text1 = "line1\nline2\nline3"
        text2 = "line1\nline2\nline3"
        
        stats = self.diff_service.get_diff_stats(text1, text2)
        
        self.assertEqual(stats['added_lines'], 0)
        self.assertEqual(stats['removed_lines'], 0)
        self.assertEqual(stats['changed_lines'], 0)
        self.assertEqual(stats['total_changes'], 0)
    
    def test_diff_stats_with_changes(self):
        """Test diff stats with changes"""
        text1 = "line1\nline2\nline3"
        text2 = "line1\nline2_modified\nline3\nline4"
        
        stats = self.diff_service.get_diff_stats(text1, text2)
        
        # Should detect changes
        self.assertTrue(stats['total_changes'] > 0)
    
    def test_diff_empty_texts(self):
        """Test diff with empty texts"""
        text1 = ""
        text2 = "line1"
        
        diff = self.diff_service.unified_diff(text1, text2)
        
        self.assertIn("+line1", diff)
    
    def test_diff_multiline_changes(self):
        """Test diff with multiple changes"""
        text1 = "line1\nline2\nline3\nline4\nline5"
        text2 = "line1\nline2_mod\nline3\nline5\nline6"
        
        stats = self.diff_service.get_diff_stats(text1, text2)
        
        # Should have additions, removals, and modifications
        self.assertTrue(stats['total_changes'] > 0)


class TestDiffEdgeCases(unittest.TestCase):
    """Test edge cases for diff service"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.diff_service = DiffService()
    
    def test_diff_whitespace_only(self):
        """Test diff with whitespace differences"""
        text1 = "line1\nline2"
        text2 = "line1\n  line2"
        
        diff = self.diff_service.unified_diff(text1, text2)
        
        # Should detect whitespace change
        self.assertIn("-line2", diff)
        self.assertIn("+  line2", diff)
    
    def test_diff_large_text(self):
        """Test diff with large texts"""
        text1 = "\n".join([f"line{i}" for i in range(1000)])
        text2 = "\n".join([f"line{i}" if i != 500 else "modified_line500" for i in range(1000)])
        
        stats = self.diff_service.get_diff_stats(text1, text2)
        
        # Should handle large texts
        self.assertTrue(stats['total_changes'] > 0)
    
    def test_diff_special_characters(self):
        """Test diff with special characters"""
        text1 = "line1\n#comment\nline2"
        text2 = "line1\n#modified_comment\nline2"
        
        diff = self.diff_service.unified_diff(text1, text2)
        
        # Should handle special characters
        self.assertIn("#comment", diff)
        self.assertIn("#modified_comment", diff)


if __name__ == "__main__":
    unittest.main()
