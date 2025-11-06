"""Diff service for comparing configurations"""
import logging
import difflib
from typing import List, Tuple
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


class DiffService:
    """Handles configuration diff operations"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load diff configuration"""
        from app.config import get_config_path
        config_path = get_config_path()
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def unified_diff(self, text1: str, text2: str, label1: str = "Before",
                    label2: str = "After") -> str:
        """
        Generate unified diff with line numbers
        
        Args:
            text1: Original text
            text2: Modified text
            label1: Label for original
            label2: Label for modified
            
        Returns:
            Unified diff string with context
        """
        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)
        
        context_lines = self.config['diff']['context_lines']
        
        diff = difflib.unified_diff(
            lines1,
            lines2,
            fromfile=label1,
            tofile=label2,
            lineterm='',
            n=context_lines
        )
        
        return '\n'.join(diff)
    
    def side_by_side_diff(self, text1: str, text2: str) -> List[Tuple[int, int, str, str, str]]:
        """
        Generate side-by-side diff data
        
        Returns:
            List of tuples: (line_num1, line_num2, line1, line2, opcode)
            Opcodes: 'equal', 'delete', 'insert', 'replace'
        """
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()
        
        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        result = []
        
        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == 'equal':
                for i in range(i1, i2):
                    result.append((i + 1, j1 + i - i1 + 1, lines1[i], lines2[j1 + i - i1], 'equal'))
            
            elif opcode == 'delete':
                for i in range(i1, i2):
                    result.append((i + 1, 0, lines1[i], '', 'delete'))
            
            elif opcode == 'insert':
                for j in range(j1, j2):
                    result.append((0, j + 1, '', lines2[j], 'insert'))
            
            elif opcode == 'replace':
                max_lines = max(i2 - i1, j2 - j1)
                for k in range(max_lines):
                    line1 = lines1[i1 + k] if i1 + k < i2 else ''
                    line2 = lines2[j1 + k] if j1 + k < j2 else ''
                    linenum1 = i1 + k + 1 if i1 + k < i2 else 0
                    linenum2 = j1 + k + 1 if j1 + k < j2 else 0
                    result.append((linenum1, linenum2, line1, line2, 'replace'))
        
        return result
    
    def get_diff_stats(self, text1: str, text2: str) -> dict:
        """
        Calculate diff statistics
        
        Returns:
            Dict with keys: added_lines, removed_lines, changed_lines, total_changes
        """
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()
        
        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        
        added = 0
        removed = 0
        changed = 0
        
        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == 'delete':
                removed += (i2 - i1)
            elif opcode == 'insert':
                added += (j2 - j1)
            elif opcode == 'replace':
                changed += max(i2 - i1, j2 - j1)
        
        return {
            'added_lines': added,
            'removed_lines': removed,
            'changed_lines': changed,
            'total_changes': added + removed + changed
        }
    
    def export_diff(self, diff_text: str, file_path: str):
        """Export diff to file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(diff_text)
            logger.info(f"Diff exported to {file_path}")
        except Exception as e:
            logger.error(f"Failed to export diff: {e}")
            raise
