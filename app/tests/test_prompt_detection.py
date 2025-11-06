"""Tests for CLI prompt detection"""
import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestPromptDetection(unittest.TestCase):
    """Test cases for prompt detection logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.prompts = ["#", ">", "(config)#", "(config-if)#"]
        self.paging_indicators = ["--More--", "-- More --", "<--- More --->"]
    
    def test_detect_privileged_prompt(self):
        """Test detection of privileged exec mode prompt (#)"""
        output = "Switch-Name#"
        
        detected = any(prompt in output for prompt in self.prompts)
        self.assertTrue(detected)
    
    def test_detect_user_prompt(self):
        """Test detection of user exec mode prompt (>)"""
        output = "Switch-Name>"
        
        detected = any(prompt in output for prompt in self.prompts)
        self.assertTrue(detected)
    
    def test_detect_config_prompt(self):
        """Test detection of config mode prompt"""
        output = "Switch-Name(config)#"
        
        detected = any(prompt in output for prompt in self.prompts)
        self.assertTrue(detected)
    
    def test_detect_interface_config_prompt(self):
        """Test detection of interface config prompt"""
        output = "Switch-Name(config-if)#"
        
        detected = any(prompt in output for prompt in self.prompts)
        self.assertTrue(detected)
    
    def test_detect_paging_indicator(self):
        """Test detection of paging indicators"""
        outputs = [
            "Some output\n--More--\n",
            "Some output\n-- More --\n",
            "Some output\n<--- More --->\n"
        ]
        
        for output in outputs:
            detected = any(indicator in output for indicator in self.paging_indicators)
            self.assertTrue(detected, f"Failed to detect paging in: {output}")
    
    def test_no_false_positive_prompts(self):
        """Test that normal text doesn't trigger false positives"""
        output = "This is normal configuration text without prompts"
        
        # Check for prompt at end of line only
        lines = output.split('\n')
        detected = False
        for line in lines:
            if line.strip().endswith('#') or line.strip().endswith('>'):
                if len(line.strip()) < 50:  # Short lines are likely prompts
                    detected = True
        
        self.assertFalse(detected)
    
    def test_prompt_with_hostname(self):
        """Test prompt detection with various hostnames"""
        hostnames = [
            "ATI-Switch",
            "Core-SW-01",
            "Access-SW-Floor2",
            "ATI-CORE-SW"
        ]
        
        for hostname in hostnames:
            output = f"{hostname}#"
            detected = any(prompt in output for prompt in self.prompts)
            self.assertTrue(detected, f"Failed to detect prompt for: {hostname}")
    
    def test_clean_output_removes_prompts(self):
        """Test cleaning output removes prompts"""
        output = "Switch#show running-config\nBuilding configuration...\nSwitch#"
        
        lines = output.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip command echo
            if "show running-config" in line:
                continue
            
            # Skip prompt lines
            if line.strip().endswith('#') and len(line.strip()) < 50:
                continue
            
            cleaned_lines.append(line)
        
        cleaned = '\n'.join(cleaned_lines)
        
        # Should not contain prompt at end
        self.assertFalse(cleaned.strip().endswith('#'))
    
    def test_clean_output_removes_paging(self):
        """Test cleaning output removes paging indicators"""
        output = "Config line 1\n--More--\nConfig line 2"
        
        lines = output.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip paging indicators
            if any(indicator in line for indicator in self.paging_indicators):
                continue
            cleaned_lines.append(line)
        
        cleaned = '\n'.join(cleaned_lines)
        
        self.assertNotIn("--More--", cleaned)
        self.assertIn("Config line 1", cleaned)
        self.assertIn("Config line 2", cleaned)
    
    def test_detect_enable_password_prompt(self):
        """Test detection of enable password prompt"""
        prompts = ["password:", "Password:", "Enable password:"]
        
        output = "Switch>enable\nPassword:"
        
        detected = any(p.lower() in output.lower() for p in prompts)
        self.assertTrue(detected)
    
    def test_multiple_prompts_in_output(self):
        """Test handling output with multiple prompts"""
        output = """
        Switch>enable
        Password:
        Switch#show running-config
        Building configuration...
        Switch#
        """
        
        # Count prompts
        prompt_count = sum(1 for line in output.split('\n') 
                          if line.strip().endswith('#') or line.strip().endswith('>'))
        
        self.assertGreater(prompt_count, 0)


class TestOutputNormalization(unittest.TestCase):
    """Test output normalization logic"""
    
    def test_normalize_line_endings_crlf(self):
        """Test normalization of CRLF line endings"""
        text = "line1\r\nline2\r\nline3"
        normalized = text.replace('\r\n', '\n')
        
        self.assertEqual(normalized, "line1\nline2\nline3")
    
    def test_normalize_line_endings_cr(self):
        """Test normalization of CR line endings"""
        text = "line1\rline2\rline3"
        normalized = text.replace('\r', '\n')
        
        self.assertEqual(normalized, "line1\nline2\nline3")
    
    def test_remove_trailing_whitespace(self):
        """Test removal of trailing whitespace"""
        text = "line1   \nline2\t\nline3  "
        
        lines = [line.rstrip() for line in text.split('\n')]
        normalized = '\n'.join(lines)
        
        self.assertEqual(normalized, "line1\nline2\nline3")
    
    def test_remove_empty_lines_at_edges(self):
        """Test removal of empty lines at start and end"""
        text = "\n\nline1\nline2\nline3\n\n"
        
        lines = [line.rstrip() for line in text.split('\n')]
        
        # Remove empty lines at start
        while lines and not lines[0].strip():
            lines.pop(0)
        
        # Remove empty lines at end
        while lines and not lines[-1].strip():
            lines.pop()
        
        normalized = '\n'.join(lines)
        
        self.assertEqual(normalized, "line1\nline2\nline3")


if __name__ == "__main__":
    unittest.main()
