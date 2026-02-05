# Serena + Claude Code Setup

This repository contains example configuration files demonstrating meaningful changes and optimizations for running Serena effectively with Claude Code.

## Contents

### `.claude/`
Claude Code project configuration including:
- `settings.json` - Project-specific Claude Code settings
- `hooks/` - Custom hooks for enhanced workflow:
  - `serena-gate.py` - Ensures Serena initialization before operations
  - `block-bash-use-serena.py` - Enforces Serena tool usage over bash commands
  - `remind-run-tests.py` - Test execution reminders

### `.serena/`
Serena-specific configuration:
- `memories/critical_behaviors.md` - This gets read in before all tool calls

### `bash_scripts/`
Helper bash aliases and functions to streamline Claude Code + Serena usage:

- **`claudette` alias**: Run Claude Code with Serena disabled
  ```bash
  alias claudette='SKIP_SERENA=true claude'
  ```

- **`cc` function**: Run Claude Code with automatic `.local.env` loading
  ```bash
  cc() {
    clear
    (
      if [ -f .local.env ]; then
        set -a
        source .local.env
        set +a
      else
        echo "No .local.env file found"
      fi
      claude "$@"
    )
  }
  ```

### `.local.env.example`
Example environment variable configuration file. Copy to `.local.env` and customize for your setup.

## Notes

Source the bash aliases in your `.bashrc` or `.zshrc`:
```bash
source /path/to/bash_scripts/alias.sh
```

Copy `.local.env.example` to `.local.env` and configure as needed

Use `cc` to launch Claude Code with environment variables loaded
Use `claudette` when you need to run Claude Code without Serena
 
Setup serena as per documentation (I just used the claude code pluging) and then add the files from this project. settings.json will need to be merged with existing settings.json if claude has already been initilised.

Local env variable is to use the new claude code feature to try and delay MCP tool use until necessary
https://code.claude.com/docs/en/mcp#scale-with-mcp-tool-search