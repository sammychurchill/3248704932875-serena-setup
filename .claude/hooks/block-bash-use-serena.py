#!/usr/bin/env python3
"""Block bash commands that should use Serena tools or npm scripts instead."""
import sys
import json
import re
import os
from pathlib import Path


def is_bypassed():
    """Check if Serena hooks should be bypassed via environment variable."""
    return os.environ.get('SKIP_SERENA', '').lower() in ('1', 'true', 'yes')


def is_in_git_repo():
    """Check if current directory is in a git repository."""
    import subprocess
    try:
        result = subprocess.run(['git', 'rev-parse', '--git-dir'],
                                capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


# Commands that read/search files - should use Serena tools
FILE_READING_COMMANDS = {
    'cat', 'head', 'tail', 'less', 'more',
    'grep', 'rg', 'ag', 'ack',
    'find', 'fd',
    'ls', 'tree',
    'sed', 'awk', 'cut', 'sort', 'uniq',
}

# Direct tool invocations that should use npm scripts
TOOLS_REQUIRING_NPM_SCRIPTS = {
    'vitest', 'jest', 'mocha', 'ava',  # Testing
    'eslint', 'prettier', 'tsc',  # Linting/Type checking
    'vite', 'webpack', 'rollup', 'esbuild',  # Bundlers
    'wrangler', 'vercel', 'netlify',  # Deployment
    'drizzle-kit', 'prisma', 'typeorm',  # ORMs
    'tsx', 'ts-node',  # TypeScript runners
}

# Always allowed commands (system operations)
ALWAYS_ALLOWED = {
    'git',  # Version control
    'cd', 'pwd', 'mkdir', 'touch', 'rm', 'mv', 'cp', 'chmod', 'chown',  # Basic file ops
    'echo', 'printf',  # Output
    'which', 'whereis', 'command',  # Command lookup
    'env', 'export', 'unset',  # Environment
    'curl', 'wget',  # HTTP requests (when needed for API calls, not file reading)
}

# npm commands that are shorthands for scripts (validate against package.json)
NPM_SCRIPT_SHORTHANDS = {
    'test', 'start', 'build', 'dev'
}

# npm built-in/lifecycle commands (always allowed, don't validate)
NPM_LIFECYCLE_COMMANDS = {
    'install', 'ci', 'update', 'uninstall', 'init', 'audit', 'fund', 'doctor', 'version'
}

# Message templates
FILE_READING_MESSAGE = """🚫 **Use Serena tools instead of `{cmd_name}`**

The command `{cmd_name}` is for reading files. Use Serena's semantic code tools for better efficiency.

**For non-code files:**
- ✅ Use `Read` tool

**For code files:**
- ✅ `mcp__plugin_serena_serena__get_symbols_overview` - Get code structure overview
- ✅ `mcp__plugin_serena_serena__find_symbol` with `include_body=true` - Read specific symbols

**Why Serena?**
- 📊 Token-efficient (doesn't read entire files)
- 🎯 Semantic understanding of code structure"""

CODE_SEARCH_MESSAGE = """🚫 **Use Serena tools instead of `{cmd_name}`**

The command `{cmd_name}` is for searching code. Use Serena's semantic search tools instead.

**For pattern/regex search:**
- ✅ `mcp__plugin_serena_serena__search_for_pattern` - Search with regex patterns

**For symbol search:**
- ✅ `mcp__plugin_serena_serena__find_symbol` - Find classes, methods, functions by name
- ✅ `mcp__plugin_serena_serena__find_referencing_symbols` - Find where symbols are used

**Why Serena?**
- 🎯 Semantic understanding of code structure
- ⚡ Faster for large codebases"""

FILE_FINDING_MESSAGE = """🚫 **Use Serena tools instead of `{cmd_name}`**

The command `{cmd_name}` is for finding/listing files. Use Serena's file tools instead.

**For finding files by pattern:**
- ✅ `mcp__plugin_serena_serena__find_file` - Find files with file_mask (e.g., "*.ts")

**For listing directories:**
- ✅ `mcp__plugin_serena_serena__list_dir` - List with recursive option

**Why Serena?**
- 🔍 Respects .gitignore automatically
- 📊 More structured output"""

TEXT_EDITING_MESSAGE = """🚫 **Use editing tools instead of `{cmd_name}`**

The command `{cmd_name}` is for text processing. Use proper editing tools instead.

**For code editing:**
- ✅ `Edit` tool - For line-based edits
- ✅ `mcp__plugin_serena_serena__replace_symbol_body` - For replacing entire symbols

**For text processing:**
- ✅ Use `Read` tool + process in code instead of shell commands

**Why proper editing tools?**
- 🛡️ Safer (no accidental file corruption)
- 🎯 More precise and verifiable"""

USE_NPM_SCRIPTS_MESSAGE = """🚫 **Use npm scripts instead of `{cmd_name}`**

Direct tool invocations should use npm scripts from package.json.

**Use instead:**
- ✅ {npm_equivalent}

**Why npm scripts?**
- 📦 Consistent across environments
- 🔧 Configured in package.json
- 🛡️ Prevents direct tool version conflicts
- 📝 Self-documenting (scripts are listed in package.json)

**Available scripts:**
Run `npm run` to see all available scripts."""

SCRIPT_NOT_FOUND_MESSAGE = """🚫 **Script '{script_name}' not found in package.json**

The npm script '{script_name}' doesn't exist in package.json.

**Available scripts:**
{available_scripts}

**Did you mean?**
Check package.json for the correct script name."""


def get_serena_message_for_command(cmd_name):
    """Get the appropriate Serena message for a given command."""
    # File reading commands
    if cmd_name in {'cat', 'head', 'tail', 'less', 'more'}:
        return FILE_READING_MESSAGE.format(cmd_name=cmd_name)

    # Code search commands
    if cmd_name in {'grep', 'rg', 'ag', 'ack'}:
        return CODE_SEARCH_MESSAGE.format(cmd_name=cmd_name)

    # File finding/listing commands
    if cmd_name in {'find', 'fd', 'ls', 'tree'}:
        return FILE_FINDING_MESSAGE.format(cmd_name=cmd_name)

    # Text editing/processing commands
    if cmd_name in {'sed', 'awk', 'cut', 'sort', 'uniq'}:
        return TEXT_EDITING_MESSAGE.format(cmd_name=cmd_name)

    # Fallback (should not happen if FILE_READING_COMMANDS is kept in sync)
    return FILE_READING_MESSAGE.format(cmd_name=cmd_name)


def load_package_json():
    """Load package.json to validate npm scripts."""
    try:
        package_json_path = Path(os.environ.get('CLAUDE_PROJECT_DIR', '.')) / 'package.json'
        if package_json_path.exists():
            with open(package_json_path) as f:
                data = json.load(f)
                return data.get('scripts', {})
    except Exception:
        pass
    return {}


def get_command_name(command):
    """Extract the base command from a bash command string."""
    # Remove leading whitespace and pipes
    command = command.strip().split('|')[0].strip()
    # Get first word (the command)
    parts = command.split()
    if not parts:
        return None

    # Handle 'npx' specially
    if parts[0] == 'npx' and len(parts) > 1:
        return parts[1]

    return parts[0]


def parse_npm_command(command):
    """Parse npm command to extract script name."""
    parts = command.strip().split()
    if len(parts) < 2:
        return None

    # Handle 'npm run <script>' - explicit script invocation
    if parts[1] == 'run' and len(parts) > 2:
        return parts[2]

    # Handle npm shorthand commands (npm test, npm start, etc.)
    if parts[1] in NPM_SCRIPT_SHORTHANDS:
        return parts[1]

    # Handle npm built-in/lifecycle commands (npm install, npm ci, etc.)
    if parts[1] in NPM_LIFECYCLE_COMMANDS:
        return '__npm_lifecycle__'

    return None


def main():
    input_data = json.load(sys.stdin)

    # Bypass if SKIP_SERENA is set or not in a git repository
    if is_bypassed() or not is_in_git_repo():
        print(json.dumps({}))
        sys.exit(0)

    # Only run on PreToolUse events for Bash tool
    hook_event = input_data.get('hook_event_name', '')
    tool_name = input_data.get('tool_name', '')

    if hook_event != 'PreToolUse' or tool_name != 'Bash':
        print(json.dumps({}))
        sys.exit(0)

    # Get the bash command
    tool_input = input_data.get('tool_input', {})
    command = tool_input.get('command', '').strip()

    if not command:
        print(json.dumps({}))
        sys.exit(0)

    cmd_name = get_command_name(command)
    if not cmd_name:
        print(json.dumps({}))
        sys.exit(0)

    # Check 1: Block file-reading commands → Use Serena
    if cmd_name in FILE_READING_COMMANDS:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Command '{cmd_name}' should use Serena tools instead"
            },
            "systemMessage": get_serena_message_for_command(cmd_name)
        }
        print(json.dumps(result))
        sys.exit(2)

    # Check 2: Block direct tool invocations → Use npm scripts
    if cmd_name in TOOLS_REQUIRING_NPM_SCRIPTS:
        npm_equivalent = {
            'vitest': 'npm test or npm run test:watch',
            'eslint': 'npm run lint or npm run lint:fix',
            'vite': 'npm run dev or npm run build',
            'wrangler': 'npm run deploy or npm run db:migrate:local',
            'drizzle-kit': 'npm run db:studio'
        }.get(cmd_name, 'npm run <script-name>')

        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Use npm scripts instead of direct '{cmd_name}' invocation"
            },
            "systemMessage": USE_NPM_SCRIPTS_MESSAGE.format(
                cmd_name=cmd_name,
                npm_equivalent=npm_equivalent
            )
        }
        print(json.dumps(result))
        sys.exit(2)

    # Check 3: Validate npm commands against package.json
    if cmd_name == 'npm':
        script_name = parse_npm_command(command)

        if script_name == '__npm_lifecycle__':
            # Allow npm install, ci, etc.
            print(json.dumps({}))
            sys.exit(0)

        if script_name:
            available_scripts = load_package_json()

            if script_name not in available_scripts:
                available = '\n'.join(f"  - npm run {s}" for s in sorted(available_scripts.keys()))
                result = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"Script '{script_name}' not found in package.json"
                    },
                    "systemMessage": SCRIPT_NOT_FOUND_MESSAGE.format(
                        script_name=script_name,
                        available_scripts=available
                    )
                }
                print(json.dumps(result))
                sys.exit(2)

    # Check 4: Allow explicitly allowed commands
    if cmd_name in ALWAYS_ALLOWED:
        print(json.dumps({}))
        sys.exit(0)

    # Check 5: Allow npm (already validated above)
    if cmd_name == 'npm':
        print(json.dumps({}))
        sys.exit(0)

    # Default: Allow (for system commands we haven't categorized)
    print(json.dumps({}))
    sys.exit(0)


if __name__ == '__main__':
    main()
