from __future__ import annotations

import re


def generate_rollback_script(raw_diff: str, switch_name: str = "switch") -> str:
    """Generate CLI rollback commands from unified diff (Baseline vs Current).

    In unified diff:
      lines with '-' were in Baseline, missing in Current (need to be re-applied/restored)
      lines with '+' were added in Current (need to be removed or negated with 'no')
    """
    lines = raw_diff.splitlines()
    revert_commands: list[str] = []

    # Track interface / block context to group rollback commands
    current_context: str | None = None
    context_commands: list[str] = []

    def flush_context():
        nonlocal current_context, context_commands
        if current_context and context_commands:
            revert_commands.append(current_context)
            revert_commands.extend([f"  {cmd}" for cmd in context_commands])
            revert_commands.append("  exit")
        current_context = None
        context_commands = []

    for line in lines:
        if line.startswith(("---", "+++", "@@")):
            continue

        # Added line in current config -> Needs to be negated / removed
        if line.startswith("+"):
            content = line[1:].strip()
            if not content or content.startswith("!") or content.startswith("#"):
                continue

            # Check if this starts a block context (e.g. "interface GigabitEthernet0/1")
            if re.match(r"^(interface|router|line)\s+", content, re.IGNORECASE):
                flush_context()
                current_context = content
                continue

            # Regular commands or standalone objects like "vlan 50"
            if content.lower().startswith("no "):
                cmd = content[3:].strip()
            else:
                cmd = f"no {content}"

            if current_context:
                context_commands.append(cmd)
            else:
                revert_commands.append(cmd)

        # Removed line (was in baseline) -> Needs to be restored
        elif line.startswith("-"):
            content = line[1:].strip()
            if not content or content.startswith("!") or content.startswith("#"):
                continue

            if re.match(r"^(interface|router|line)\s+", content, re.IGNORECASE):
                flush_context()
                current_context = content
                continue

            if current_context:
                context_commands.append(content)
            else:
                revert_commands.append(content)

    flush_context()

    header = [
        f"! ===========================================================",
        f"! REMEDIATION ROLLBACK SCRIPT FOR {switch_name.upper()}",
        f"! Standard ISO 27001 A.8.9 - Configuration Management Reversion",
        f"! CAUTION: Review before applying to physical device.",
        f"! ===========================================================",
        "configure terminal",
    ]
    footer = [
        "end",
        "write memory",
        f"! End of rollback script for {switch_name}",
    ]

    if not revert_commands:
        return "\n".join(header + ["! No direct CLI rollback command detected from diff."] + footer)

    return "\n".join(header + revert_commands + footer)
