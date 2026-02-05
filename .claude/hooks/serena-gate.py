#!/usr/bin/env python3
"""Enforce Serena activation at session start.

Requires BOTH activate_project AND initial_instructions before unlocking tools.
"""
import os
import sys
import json
import hashlib
import fcntl

MARKER_DIR = "/tmp"
ACTIVATION_TOOL = "mcp__plugin_serena_serena__activate_project"
INSTRUCTIONS_TOOL = "mcp__plugin_serena_serena__initial_instructions"
ONBOARDING_TOOL = "mcp__plugin_serena_serena__onboarding"
READ_MEMORY_TOOL = "mcp__plugin_serena_serena__read_memory"

# Tools allowed before full initialization
ALWAYS_ALLOWED = {
    ACTIVATION_TOOL,
    INSTRUCTIONS_TOOL,
    ONBOARDING_TOOL,
    READ_MEMORY_TOOL,
    "ToolSearch",
}


def is_bypassed():
    return os.environ.get('SKIP_SERENA', '').lower() in ('1', 'true', 'yes')


def is_in_git_repo():
    import subprocess
    try:
        result = subprocess.run(['git', 'rev-parse', '--git-dir'],
                                capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def get_git_root():
    import subprocess
    try:
        result = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return os.getcwd()


def get_session_id(input_data):
    """Return session_id from input or None if not present.

    No fallback - each conversation must have its own session.
    /new = new session_id = requires re-initialization
    /resume = same session_id = keeps initialization state
    """
    return input_data.get('session_id')


def get_project_name():
    return os.path.basename(get_git_root())


def get_marker_path(input_data):
    session_id = get_session_id(input_data)
    if not session_id:
        return None
    return f"{MARKER_DIR}/.serena-session-{session_id}"


def read_marker(input_data):
    path = get_marker_path(input_data)
    if not path or not os.path.exists(path):
        return {"activated": False, "instructions_read": False, "critical_behaviors_read": False}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"activated": False, "instructions_read": False, "critical_behaviors_read": False}


def update_marker(input_data, key, value):
    """Atomically update a single key in the marker file using file locking."""
    path = get_marker_path(input_data)
    if not path:
        return {"activated": False, "instructions_read": False, "critical_behaviors_read": False}

    # Use 'a+' to create file if missing, then lock
    with open(path, 'a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # Blocking exclusive lock
        f.seek(0)
        content = f.read()
        try:
            state = json.loads(content) if content else {}
        except json.JSONDecodeError:
            state = {}
        state[key] = value
        f.seek(0)
        f.truncate()
        json.dump(state, f)
    # Lock auto-released when file closes
    return state


def handle_pretooluse(input_data):
    tool_name = input_data.get('tool_name', '')

    if is_bypassed() or not is_in_git_repo():
        return {}

    state = read_marker(input_data)

    # Track init tool invocations as "pending" (atomic update)
    if tool_name == ACTIVATION_TOOL:
        update_marker(input_data, "activated", "pending")
        return {}

    if tool_name == INSTRUCTIONS_TOOL:
        update_marker(input_data, "instructions_read", "pending")
        return {}

    if tool_name == READ_MEMORY_TOOL:
        tool_input = input_data.get('tool_input', {})
        memory_name = tool_input.get('memory_file_name', '') or tool_input.get('memory_name', '')
        if memory_name == 'critical_behaviors':
            update_marker(input_data, "critical_behaviors_read", "pending")
        return {}

    # Allow other tools in ALWAYS_ALLOWED
    if tool_name in ALWAYS_ALLOWED:
        return {}

    project_name = get_project_name()

    # Block until ALL THREE are at least pending (invoked)
    activated = state.get("activated")
    instructions = state.get("instructions_read")
    critical_behaviors = state.get("critical_behaviors_read")

    if not (activated and instructions and critical_behaviors):
        missing = []
        if not activated:
            missing.append(f"mcp__plugin_serena_serena__activate_project(project='{project_name}')")
        if not instructions:
            missing.append("mcp__plugin_serena_serena__initial_instructions()")
        if not critical_behaviors:
            missing.append("mcp__plugin_serena_serena__read_memory(memory_file_name='critical_behaviors')")

        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Tool blocked. Still need to call: {' AND '.join(missing)}"
            },
            "systemMessage": f"Tool blocked. Still need to call: {' AND '.join(missing)}"
        }

    return {}


def handle_posttooluse(input_data):
    tool_name = input_data.get('tool_name', '')
    tool_error = input_data.get('tool_error')

    if is_bypassed() or not is_in_git_repo():
        return {}

    if tool_name == ACTIVATION_TOOL:
        # Update activated state (atomic)
        value = False if tool_error else True
        state = update_marker(input_data, "activated", value)
        # Also store project name (atomic)
        state = update_marker(input_data, "project", get_project_name())

        if state.get("activated") == True and state.get("instructions_read") == True and state.get("critical_behaviors_read") == True:
            return {"systemMessage": "✓ Serena fully initialized. All tools unlocked."}
        elif state.get("activated") == True:
            remaining = []
            if state.get("instructions_read") not in (True, "pending"):
                remaining.append("initial_instructions()")
            if state.get("critical_behaviors_read") not in (True, "pending"):
                remaining.append("read_memory(memory_name='critical_behaviors')")
            if remaining:
                return {"systemMessage": f"✓ Serena activated. Still need: {', '.join(remaining)}"}
            return {"systemMessage": "✓ Serena activated. Waiting for other steps to complete."}
        return {}

    if tool_name == INSTRUCTIONS_TOOL:
        # Update instructions_read state (atomic)
        value = False if tool_error else True
        state = update_marker(input_data, "instructions_read", value)

        if state.get("activated") == True and state.get("instructions_read") == True and state.get("critical_behaviors_read") == True:
            return {"systemMessage": "✓ Serena fully initialized. All tools unlocked."}
        elif state.get("instructions_read") == True:
            remaining = []
            if state.get("activated") not in (True, "pending"):
                remaining.append("activate_project()")
            if state.get("critical_behaviors_read") not in (True, "pending"):
                remaining.append("read_memory(memory_name='critical_behaviors')")
            if remaining:
                return {"systemMessage": f"✓ Instructions read. Still need: {', '.join(remaining)}"}
            return {"systemMessage": "✓ Instructions read. Waiting for other steps to complete."}
        return {}

    if tool_name == READ_MEMORY_TOOL:
        tool_input = input_data.get('tool_input', {})
        memory_name = tool_input.get('memory_file_name', '') or tool_input.get('memory_name', '')
        if memory_name == 'critical_behaviors':
            value = False if tool_error else True
            state = update_marker(input_data, "critical_behaviors_read", value)

            if state.get("activated") == True and state.get("instructions_read") == True and state.get("critical_behaviors_read") == True:
                return {"systemMessage": "✓ Serena fully initialized. All tools unlocked."}
            elif state.get("critical_behaviors_read") == True:
                remaining = []
                if state.get("activated") not in (True, "pending"):
                    remaining.append("activate_project()")
                if state.get("instructions_read") not in (True, "pending"):
                    remaining.append("initial_instructions()")
                if remaining:
                    return {"systemMessage": f"✓ critical_behaviors read. Still need: {', '.join(remaining)}"}
                return {"systemMessage": "✓ critical_behaviors read. Waiting for other steps to complete."}
        return {}

    return {}


def main():
    input_data = json.load(sys.stdin)
    hook_event = input_data.get('hook_event_name', '')

    # Debug logging
    debug_log = "/tmp/serena-gate-debug.log"
    with open(debug_log, "a") as f:
        f.write(f"\n=== Hook Called ===\n")
        f.write(f"Event: {hook_event}\n")
        f.write(f"Tool: {input_data.get('tool_name', 'N/A')}\n")
        f.write(f"Session ID: {input_data.get('session_id', 'N/A')}\n")
        f.write(f"Input data: {json.dumps(input_data, indent=2)}\n")

    if hook_event == 'PreToolUse':
        result = handle_pretooluse(input_data)
    elif hook_event == 'PostToolUse':
        result = handle_posttooluse(input_data)
    else:
        result = {}

    # Log result
    with open(debug_log, "a") as f:
        f.write(f"Result: {json.dumps(result, indent=2)}\n")

    print(json.dumps(result))

    if result.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny':
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()