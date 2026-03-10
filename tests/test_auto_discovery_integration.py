#!/usr/bin/env python3
"""
Test the complete auto-discovery integration with skill pattern gate.
"""

import sys

# Test imports
try:
    from skill_guard.skill_auto_discovery import (
        discover_all_skills,
        get_skill_config,
    )
    print("✅ Auto-discovery module imports successfully")
except ImportError as e:
    print(f"❌ Failed to import auto-discovery: {e}")
    sys.exit(1)

# Test 1: Discover all skills
print("\n=== Test 1: Discover All Skills ===")
all_skills = discover_all_skills()
print(f"✅ Discovered {len(all_skills)} skills")

# Test 2: Knowledge skills have no tools
print("\n=== Test 2: Knowledge Skills ===")
knowledge_skills = ["cks", "search", "constraints", "standards"]
for skill in knowledge_skills:
    config = get_skill_config(skill, {})
    tools = config.get('tools', [])
    assert tools == [], f"{skill} should have no tools, got {tools}"
    print(f"✅ {skill}: no enforcement (knowledge skill)")

print("\n✅ All tests passed!")
