# Codebase MCP Server

A Model Context Protocol (MCP) server that provides intelligent search and navigation capabilities for Python, SQL, and Markdown codebases. Built to help LLMs and AI assistants understand and explore large codebases efficiently.

## Features

- **Fast Indexing**: AST-based parsing of Python files, SQL pattern matching, and Markdown content extraction
- **Semantic Search**: Find functions, classes, routes, models, tables, and documentation across your codebase
- **Flask Route Discovery**: Locate web endpoints and their handlers
- **ORM Model Navigation**: Understand database models (SQLAlchemy, Flask-SQLAlchemy)
- **SQL Schema Exploration**: View table definitions and migration history
- **Component Listing**: Get overviews of routes, models, tables, and key classes
- **File Explanations**: Detailed summaries of file purposes and dependencies

## Architecture

- **Indexer**: Pre-builds a JSON index of your codebase (~1 second for 3000+ components)
- **Server**: Provides 7 MCP tools for code exploration
- **Storage**: 4-5MB disk footprint, ~64MB RAM per instance
- **Performance**: Lazy-loaded index with efficient search scoring

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager (or pip)

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/codebase-mcp-server.git
cd codebase-mcp-server

# Install dependencies
uv pip install -e .
# Or with pip:
pip install -e .
```

## Configuration

### VS Code Integration

Create or edit `.vscode/mcp.json` in your workspace:

```json
{
  "mcpServers": {
    "codebase-search": {
      "command": "/absolute/path/to/your/project/.venv/bin/python",
      "args": [
        "/absolute/path/to/codebase-mcp-server/server.py",
        "--codebase",
        "${workspaceFolder}"
      ]
    }
  }
}
```

### Claude Desktop Integration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "codebase-search": {
      "command": "/absolute/path/to/your/project/.venv/bin/python",
      "args": [
        "/absolute/path/to/codebase-mcp-server/server.py",
        "--codebase",
        "/absolute/path/to/your/project"
      ]
    }
  }
}
```

## Available Tools

### 1. `search_code`
Search for functions, classes, routes, models, tables, or documentation
- **Parameters**: `query` (string), `type` (optional: function, class, route, model, table, file), `limit` (default: 10)
- **Returns**: Ranked search results with file paths and locations

### 2. `find_route`
Find Flask routes by path or handler name
- **Parameters**: `route` (path like `/users` or function name)
- **Returns**: Route definition with decorator and handler code

### 3. `find_model`
Locate database model classes
- **Parameters**: `model_name` (e.g., `User`, `Product`)
- **Returns**: Model class definition with fields and relationships

### 4. `find_table`
Find database tables and view SQL definitions
- **Parameters**: `table_name` (e.g., `users`, `products`)
- **Returns**: SQL CREATE TABLE/VIEW statements

### 5. `list_components`
List all components of a specific type
- **Parameters**: `component_type` (route, model, table, class)
- **Returns**: Overview of all matching components

### 6. `explain_file`
Get detailed information about a specific file
- **Parameters**: `filepath` (relative path)
- **Returns**: Purpose, main functions/classes, dependencies

### 7. `rebuild_index`
Rebuild the codebase index from scratch
- **Parameters**: None
- **Returns**: Confirmation with component count

## Usage Examples

### In VS Code with GitHub Copilot Chat

**Important**: Use the `@workspace` prefix to activate MCP tools. Without it, Copilot won't use your indexed codebase.

```
@workspace find the user authentication route
@workspace list all database models
@workspace explain the database helper module
@workspace search for email validation functions
```

### In Claude Desktop

Claude Desktop automatically uses available MCP tools - no special prefix needed:

```
Find all functions related to email validation
Show me the User model definition
List all API routes in the codebase
```

## Indexing Details

The indexer processes:
- **Python files**: Functions, classes, decorators, docstrings
- **SQL files**: CREATE TABLE/VIEW statements, stored procedures
- **Markdown files**: Headers and content for documentation search

### Excluded Directories (default)
- `.venv`, `venv`, `.git`, `__pycache__`
- `node_modules`, `.pytest_cache`, `.mypy_cache`

### Customization

Edit the `DEFAULT_EXCLUDE_PATTERNS` in `indexer.py` to change what's indexed.

## Git Integration

The precinct repository uses a pre-commit hook to auto-rebuild the index:

```bash
#!/bin/bash
# .git/hooks/pre-commit
if git diff --cached --name-only | grep -qE '\.(py|sql|md)$'; then
    python mcp_servers/precinct_codebase/indexer.py
    git add mcp_servers/precinct_codebase/codebase_index.json
fi
```

## Testing

```bash
pytest test_indexer.py -v
```

Test coverage includes:
- Python/SQL/Markdown indexing
- Search functionality with scoring
- Exclude patterns validation
- Production index validation

## Performance

- **Indexing**: ~1 second for 3000+ components
- **Disk**: 4-5MB for pre-built index
- **Memory**: ~64MB RAM per server instance
- **Search**: Sub-millisecond query response

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please submit issues and pull requests on GitHub.

## Support

For issues, questions, or feature requests, please open a GitHub issue.
