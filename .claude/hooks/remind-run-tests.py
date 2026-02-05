#!/usr/bin/env python3
"""Remind to run tests after editing TypeScript files."""
import sys
import json
import re


def main():
    input_data = json.load(sys.stdin)

    # Only run on PostToolUse events for file editing tools
    hook_event = input_data.get('hook_event_name', '')
    tool_name = input_data.get('tool_name', '')

    if hook_event != 'PostToolUse' or tool_name not in ['Edit', 'Write', 'MultiEdit']:
        print(json.dumps({}))
        sys.exit(0)

    # Check if tool errored (don't remind if edit failed)
    if input_data.get('tool_error'):
        print(json.dumps({}))
        sys.exit(0)

    # Get the file path
    tool_input = input_data.get('tool_input', {})
    file_path = tool_input.get('file_path', '')

    # Check if it's a TypeScript file
    if not re.search(r'\.ts$', file_path):
        print(json.dumps({}))
        sys.exit(0)

    # Show reminder message
    result = {
        "systemMessage": """🧪 **Reminder: Run tests after editing TypeScript files**

You've modified a TypeScript file. Don't forget to verify your changes with tests!

## Run the appropriate test command:

**If you edited a test file** (e.g., `*.test.ts`):
```bash
npm test -- --testPathPattern=<filename>
```
Replace `<filename>` with the specific test file you edited.

**If you edited a source file** (e.g., any `.ts` file):
```bash
npm test --watchAll=false
```
This runs all tests to ensure nothing broke.

## Testing Best Practices:
- ✅ Run tests after every significant change
- ✅ Ensure tests pass before committing
- ✅ Write new tests for new functionality
- ✅ Update tests when changing behavior

**Quick test commands:**
- `npm run test` - Run all tests
- `npm run test:watch` - Run tests in watch mode
- `npm test -- --testPathPattern=myfile` - Run specific test file"""
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == '__main__':
    main()
