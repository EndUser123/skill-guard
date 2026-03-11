#!/usr/bin/env python3
"""Test skill invocation indicator."""

import sys

# Add paths
sys.path.insert(0, "P:/.claude/hooks")
sys.path.insert(0, "P:/packages/skill-guard/src")
sys.path.insert(0, "P:/.claude/hooks/UserPromptSubmit_modules")

# Import the updated module
import UserPromptSubmit_modules.breadcrumb_init as breadcrumb_module
from UserPromptSubmit_modules.base import HookContext


def test_skill_invocation_indicator():
    """Test that skill invocation shows visual indicator."""
    print("Testing skill invocation indicator...")
    print()

    # Test with /gto command
    prompt = "/gto"
    context = HookContext(
        prompt=prompt,
        data={"session_id": "test", "terminal_id": "test"}
    )

    result = breadcrumb_module.breadcrumb_init_hook(context)

    print(f"Prompt: {prompt}")
    print(f"Result has context: {result.context is not None}")
    print()

    if result.context:
        print("Context output:")
        print(result.context)
        print()

        # Extract additionalContext if it's a dict
        context_text = result.context
        if isinstance(result.context, dict):
            context_text = result.context.get("additionalContext", "")

        # Check for 🔧 emoji
        if "🔧" in context_text:
            print("✅ SUCCESS: Skill invocation indicator present!")
        else:
            print("❌ FAIL: No 🔧 emoji found")

        # Check for "Invoking Skill" text
        if "Invoking Skill" in context_text:
            print("✅ SUCCESS: 'Invoking Skill' text present!")
        else:
            print("❌ FAIL: No 'Invoking Skill' text found")
    else:
        print("❌ FAIL: No context returned")

    return result.context is not None

if __name__ == "__main__":
    success = test_skill_invocation_indicator()
    sys.exit(0 if success else 1)
