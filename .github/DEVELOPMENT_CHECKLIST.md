# Development Checklist

This checklist ensures all code changes meet project quality standards before committing.

## Pre-Commit Checklist

Run these commands before every commit:

### 1. Run Tests ✅
```bash
uv run pytest tests/ -v
```
**Expected**: All tests pass (268/268)

### 2. Type Checking ✅
```bash
uv run mypy src/
```
**Expected**: No errors (Success: no issues found)

### 3. Linting ✅
```bash
uv run ruff check src/ tests/
```
**Expected**: All checks passed!

### 4. Formatting ✅
```bash
uv run black --check src/ tests/
```
**Expected**: All files would be left unchanged

## Auto-Fix Commands

If checks fail, use these to auto-fix:

### Fix Formatting
```bash
uv run black src/ tests/
```

### Fix Auto-Fixable Lint Issues
```bash
uv run ruff check --fix src/ tests/
```

## Full CI Simulation

Run all checks in sequence (same as GitHub Actions):

```bash
# Install dependencies
uv sync --all-extras

# Run all checks
uv run pytest tests/ -v && \
uv run mypy src/ && \
uv run ruff check src/ tests/ && \
uv run black --check src/ tests/

echo "✅ All CI checks passed!"
```

## Common Issues and Fixes

### Issue: Tests Fail After Adding New Config Attributes

**Problem**: Mock Config objects in tests don't have new attributes

**Fix**: Add attributes to mock configs:
```python
config = MagicMock(spec=Config)
config.new_attribute = default_value
```

### Issue: F401 - Imported but Unused

**Problem**: Import statement not used in file

**Fix**: Remove the unused import or use it

### Issue: E501 - Line Too Long

**Problem**: Line exceeds 100 characters

**Fix**: Break line into multiple lines:
```python
# Bad
some_very_long_function_call(argument1, argument2, argument3, argument4, argument5)

# Good
some_very_long_function_call(
    argument1, argument2, argument3,
    argument4, argument5
)
```

### Issue: Type Errors

**Problem**: Missing type hints or incorrect types

**Fix**: Add proper type hints:
```python
def function(param: str) -> int:
    return len(param)
```

## When Adding New Features

1. **Write tests first** (TDD approach)
2. **Run tests incrementally** as you implement
3. **Check for integration points** (mocks, dependencies)
4. **Run full CI check** before committing
5. **Update documentation** if needed

## When Modifying Existing Code

1. **Run affected tests first**
   ```bash
   uv run pytest tests/unit/test_<module>.py -v
   ```

2. **Check for usages** of modified classes/functions
   ```bash
   grep -r "ClassName" tests/
   ```

3. **Update mocks** if adding required attributes

4. **Run full test suite** to catch integration issues

## Code Quality Standards

- ✅ Line length: 100 characters max
- ✅ Type hints: Required for all functions
- ✅ Docstrings: Google-style for all public APIs
- ✅ Test coverage: All new code must have tests
- ✅ No warnings: Fix all linting warnings

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/build.yml`) runs:

1. **Test Job**:
   - Install dependencies with UV
   - Run pytest
   - Run mypy type checking
   - Run ruff linting
   - Check black formatting

2. **Build Job** (only on main branch):
   - Build multi-arch Docker images
   - Push to GitHub Container Registry

**All test job checks must pass before build job runs.**

## Quick Reference

| Check | Command | Expected Output |
|-------|---------|----------------|
| Tests | `uv run pytest tests/ -v` | 268 passed |
| Types | `uv run mypy src/` | Success: no issues |
| Lint | `uv run ruff check src/ tests/` | All checks passed! |
| Format | `uv run black --check src/ tests/` | All files unchanged |

## Tips

- **Run checks frequently** - Don't wait until the end
- **Fix issues immediately** - Easier to fix when fresh
- **Use auto-fix** - Let tools fix what they can
- **Check CI logs** - GitHub Actions shows exact errors
- **Test locally first** - Faster than waiting for CI

---

**Remember**: All these checks run automatically in CI. Running them locally first saves time and catches issues earlier!
