# Contributing to skill-guard

Thank you for your interest in contributing to skill-guard! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites
- Python 3.10 or higher
- Git
- pip or uv (recommended)

### Installation

1. **Clone the repository**:
```bash
git clone https://github.com/yourusername/skill-guard.git P:/packages/skill-guard
cd P:/packages/skill-guard
```

2. **Create a virtual environment**:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install in editable mode with dev dependencies**:
```bash
pip install -e ".[dev]"
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=src/skill_guard --cov-report=term-missing
```

### Run specific test file
```bash
pytest tests/test_breadcrumb.py
```

## Code Style

This project uses:
- **Ruff** for linting and formatting
- **Line length**: 100 characters
- **Python version**: 3.10+

### Linting
```bash
ruff check src/
```

### Auto-fix linting issues
```bash
ruff check --fix src/
```

### Format code
```bash
ruff format src/
```

## Project Structure

```
skill-guard/
├── src/skill_guard/           # Main package
│   ├── breadcrumb/           # Breadcrumb verification system
│   ├── utils/                # Utilities (terminal_detection)
│   ├── skill_auto_discovery.py
│   └── skill_execution_state.py
├── tests/                     # Test suite
│   ├── test_breadcrumb.py
│   └── test_auto_discovery_integration.py
├── scripts/                   # Helper scripts
├── pyproject.toml            # Project configuration
├── README.md
└── LICENSE
```

## Making Changes

### Workflow
1. Create a new branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass: `pytest`
5. Run linting: `ruff check --fix src/`
6. Commit with clear messages
7. Push and create a pull request

### Commit Messages
- Use clear, descriptive commit messages
- Start with a verb: "Add", "Fix", "Update", "Refactor"
- Example: "Add terminal isolation for multi-terminal safety"

## Testing Guidelines

### Writing Tests
- Place tests in the `tests/` directory
- Name test files: `test_*.py`
- Name test functions: `test_*()`
- Use pytest fixtures for setup
- Test both success and failure paths

### Test Coverage
- Aim for >80% coverage
- Run `pytest --cov` to check coverage
- Add tests for new features and bug fixes

## Pull Request Process

1. **Update documentation** if you've changed functionality
2. **Add tests** for new features or bug fixes
3. **Ensure all tests pass**: `pytest`
4. **Run linting**: `ruff check --fix src/`
5. **Update CHANGELOG.md** with your changes
6. **Create PR** with a clear description of changes

## Questions?

Feel free to open an issue for questions or discussion.
