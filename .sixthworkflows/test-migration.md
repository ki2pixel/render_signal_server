---
description: Test migration integrity
---

# Migration Test Workflow

## Steps
1. Verify all rules load correctly
2. Test skill detection patterns
3. Validate workflow execution
4. Check Memory Bank functionality

## Validation Commands
```bash
# Test skills integration
grep -c "SKILL.md" .sixthrules/05-skills-integration.md

# Test workflow references
find .sixthworkflows -name "*.md" -exec grep -l "\.sixth" {} \;

# Test memory bank
ls -la memory-bank/
```

## Tools Used

- `run_command` - To execute validation commands
- `search_files` - To find workflow files
- `list_directory` - To check memory bank structure
- `read_text_file` - To verify rule loading
