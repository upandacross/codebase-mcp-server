#!/usr/bin/env python3
"""
Codebase MCP Server

Provides searchable access to Python, SQL, and Markdown codebases.
Tools: search_code, find_route, find_model, find_table, list_components, explain_file
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from indexer import CodebaseIndexer


# Initialize
PROJECT_ROOT = Path(__file__).parent.parent.parent
INDEX_PATH = Path(__file__).parent / 'codebase_index.json'

# Global indexer (lazy loaded)
_indexer: CodebaseIndexer | None = None


def get_indexer() -> CodebaseIndexer:
    """Get or load the codebase indexer."""
    global _indexer
    if _indexer is None:
        if INDEX_PATH.exists():
            _indexer = CodebaseIndexer.load_index(INDEX_PATH, PROJECT_ROOT)
        else:
            # Build index on first run
            _indexer = CodebaseIndexer(PROJECT_ROOT)
            _indexer.index_codebase()
            _indexer.save_index(INDEX_PATH)
    return _indexer


# Create MCP server
app = Server("codebase-search")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="search_code",
            description="Search the codebase for functions, classes, routes, models, tables, or documentation. "
                       "Searches across Python code, SQL files, and Markdown documentation. "
                       "For Markdown docs, searches titles and full content. "
                       "Use this to find where specific functionality is implemented or documented.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (function name, class name, concept, documentation topic, etc.)"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["function", "class", "route", "model", "table", "file"],
                        "description": "Filter by component type. Use 'file' for Markdown docs (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of results"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="find_route",
            description="Find a Flask route by path or handler name. "
                       "Use this to locate web endpoints and see their implementation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "route": {
                        "type": "string",
                        "description": "Route path (e.g., '/voters') or handler function name"
                    }
                },
                "required": ["route"]
            }
        ),
        Tool(
            name="find_model",
            description="Find a database model class by name. "
                       "Use this to understand database schema and ORM models.",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model class (e.g., 'User', 'Product')"
                    }
                },
                "required": ["model_name"]
            }
        ),
        Tool(
            name="find_table",
            description="Find a database table by name and see its SQL definition. "
                       "Use this to understand table structure and migrations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the database table (e.g., 'flippable', 'voters')"
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="list_components",
            description="List all components of a specific type in the codebase. "
                       "Use this to get an overview of routes, models, tables, or key functions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "component_type": {
                        "type": "string",
                        "enum": ["route", "model", "table", "class"],
                        "description": "Type of component to list"
                    }
                },
                "required": ["component_type"]
            }
        ),
        Tool(
            name="explain_file",
            description="Get detailed information about a specific file including its purpose, "
                       "main functions/classes, and dependencies.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Relative path to the file (e.g., 'main.py', 'models.py')"
                    }
                },
                "required": ["filepath"]
            }
        ),
        Tool(
            name="rebuild_index",
            description="Rebuild the codebase index from scratch. "
                       "Use this after making significant code changes or if search results seem stale.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """Handle tool calls."""
    
    if name == "search_code":
        indexer = get_indexer()
        query = arguments["query"]
        comp_type = arguments.get("type")
        limit = arguments.get("limit", 10)
        
        results = indexer.search(query, component_type=comp_type, limit=limit)
        
        if not results:
            return [TextContent(
                type="text",
                text=f"No results found for '{query}'"
            )]
        
        # Format results
        output = [f"🔎 Found {len(results)} results for '{query}':\n"]
        
        for i, result in enumerate(results, 1):
            output.append(f"\n{i}. **{result['type'].upper()}**: `{result['name']}`")
            output.append(f"   📄 `{result['filepath']}:{result['line_start']}-{result['line_end']}`")
            
            if result.get('signature'):
                output.append(f"   🔧 `{result['signature']}`")
            
            if result.get('parent_class'):
                output.append(f"   👪 Class: `{result['parent_class']}`")
            
            if result.get('decorators'):
                output.append(f"   🎨 Decorators: {', '.join(f'`{d}`' for d in result['decorators'])}")
            
            if result.get('docstring'):
                docstring = result['docstring'][:150]
                if len(result['docstring']) > 150:
                    docstring += "..."
                output.append(f"   📝 {docstring}")
            
            if result.get('metadata', {}).get('route_path'):
                output.append(f"   🌐 Route: `{result['metadata']['route_path']}`")
        
        return [TextContent(type="text", text="\n".join(output))]
    
    elif name == "find_route":
        indexer = get_indexer()
        route_query = arguments["route"]
        
        # Try exact match first
        if route_query in indexer.routes:
            comp = indexer.routes[route_query]
            result = _format_component(comp)
            return [TextContent(type="text", text=result)]
        
        # Search for it
        results = indexer.search(route_query, component_type='route', limit=5)
        
        if not results:
            return [TextContent(
                type="text",
                text=f"No route found for '{route_query}'"
            )]
        
        output = [f"🌐 Found {len(results)} route(s):\n"]
        for i, result in enumerate(results, 1):
            route_path = result.get('metadata', {}).get('route_path', 'N/A')
            output.append(f"\n{i}. `{result['name']}` → `{route_path}`")
            output.append(f"   📄 `{result['filepath']}:{result['line_start']}`")
            if result.get('docstring'):
                output.append(f"   📝 {result['docstring'][:100]}")
        
        return [TextContent(type="text", text="\n".join(output))]
    
    elif name == "find_model":
        indexer = get_indexer()
        model_name = arguments["model_name"]
        
        if model_name in indexer.models:
            comp = indexer.models[model_name]
            result = _format_component(comp)
            return [TextContent(type="text", text=result)]
        
        # Search for it
        results = indexer.search(model_name, component_type='model', limit=5)
        
        if not results:
            return [TextContent(
                type="text",
                text=f"No model found for '{model_name}'"
            )]
        
        output = [f"🗄️  Found {len(results)} model(s):\n"]
        for i, result in enumerate(results, 1):
            output.append(f"\n{i}. **{result['name']}**")
            output.append(f"   📄 `{result['filepath']}:{result['line_start']}`")
            bases = result.get('metadata', {}).get('bases', [])
            if bases:
                output.append(f"   🧬 Inherits: {', '.join(f'`{b}`' for b in bases)}")
            if result.get('docstring'):
                output.append(f"   📝 {result['docstring'][:100]}")
        
        return [TextContent(type="text", text="\n".join(output))]
    
    elif name == "find_table":
        indexer = get_indexer()
        table_name = arguments["table_name"]
        
        if table_name in indexer.tables:
            comp = indexer.tables[table_name]
            result = _format_component(comp)
            return [TextContent(type="text", text=result)]
        
        # Search for it
        results = indexer.search(table_name, component_type='table', limit=5)
        
        if not results:
            return [TextContent(
                type="text",
                text=f"No table found for '{table_name}'"
            )]
        
        output = [f"📊 Found {len(results)} table(s):\n"]
        for i, result in enumerate(results, 1):
            output.append(f"\n{i}. **{result['name']}**")
            output.append(f"   📄 `{result['filepath']}:{result['line_start']}-{result['line_end']}`")
        
        return [TextContent(type="text", text="\n".join(output))]
    
    elif name == "list_components":
        indexer = get_indexer()
        comp_type = arguments["component_type"]
        
        if comp_type == "route":
            items = list(indexer.routes.values())
        elif comp_type == "model":
            items = list(indexer.models.values())
        elif comp_type == "table":
            items = list(indexer.tables.values())
        elif comp_type == "class":
            items = list(indexer.classes.values())
        else:
            return [TextContent(type="text", text=f"Unknown component type: {comp_type}")]
        
        output = [f"📋 {len(items)} {comp_type}(s) in codebase:\n"]
        
        for item in sorted(items, key=lambda x: x.name)[:50]:  # Limit to 50
            output.append(f"\n• `{item.name}` → `{item.filepath}:{item.line_start}`")
            if comp_type == "route" and item.metadata.get('route_path'):
                output.append(f"  Route: `{item.metadata['route_path']}`")
        
        if len(items) > 50:
            output.append(f"\n\n... and {len(items) - 50} more. Use search_code to find specific ones.")
        
        return [TextContent(type="text", text="\n".join(output))]
    
    elif name == "explain_file":
        indexer = get_indexer()
        filepath = arguments["filepath"]
        
        # Find all components in this file
        components = [c for c in indexer.components if c.filepath == filepath]
        
        if not components:
            return [TextContent(
                type="text",
                text=f"File not found: {filepath}"
            )]
        
        # Get file component
        file_comp = next((c for c in components if c.type == 'file'), None)
        
        output = [f"📄 **{filepath}**\n"]
        
        if file_comp and file_comp.docstring:
            output.append(f"**Description**: {file_comp.docstring}\n")
        
        # Group by type
        by_type = {}
        for comp in components:
            if comp.type != 'file':
                by_type.setdefault(comp.type, []).append(comp)
        
        for comp_type, items in sorted(by_type.items()):
            output.append(f"\n**{comp_type.upper()}S** ({len(items)}):")
            for item in sorted(items, key=lambda x: x.line_start)[:20]:
                output.append(f"• `{item.name}` (line {item.line_start})")
                if item.signature:
                    output.append(f"  {item.signature}")
        
        # Show imports if available
        if file_comp and file_comp.imports:
            unique_imports = sorted(set(file_comp.imports))[:10]
            output.append(f"\n**KEY IMPORTS**: {', '.join(f'`{i}`' for i in unique_imports)}")
            if len(file_comp.imports) > 10:
                output.append(f" ...and {len(file_comp.imports) - 10} more")
        
        return [TextContent(type="text", text="\n".join(output))]
    
    elif name == "rebuild_index":
        global _indexer
        _indexer = CodebaseIndexer(PROJECT_ROOT)
        _indexer.index_codebase()
        _indexer.save_index(INDEX_PATH)
        
        stats = {
            'components': len(_indexer.components),
            'files': len(_indexer.files_indexed),
            'routes': len(_indexer.routes),
            'models': len(_indexer.models),
            'tables': len(_indexer.tables)
        }
        
        return [TextContent(
            type="text",
            text=f"✅ Index rebuilt successfully!\n\n"
                 f"• {stats['components']} components indexed\n"
                 f"• {stats['files']} files\n"
                 f"• {stats['routes']} routes\n"
                 f"• {stats['models']} models\n"
                 f"• {stats['tables']} tables"
        )]
    
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


def _format_component(comp) -> str:
    """Format a component for display."""
    output = [f"**{comp.type.upper()}**: `{comp.name}`\n"]
    output.append(f"📄 `{comp.filepath}:{comp.line_start}-{comp.line_end}`\n")
    
    if comp.signature:
        output.append(f"**Signature**: `{comp.signature}`\n")
    
    if comp.parent_class:
        output.append(f"**Class**: `{comp.parent_class}`\n")
    
    if comp.decorators:
        output.append(f"**Decorators**: {', '.join(f'`{d}`' for d in comp.decorators)}\n")
    
    if comp.metadata:
        if comp.metadata.get('route_path'):
            output.append(f"**Route**: `{comp.metadata['route_path']}`\n")
        if comp.metadata.get('bases'):
            output.append(f"**Inherits**: {', '.join(f'`{b}`' for b in comp.metadata['bases'])}\n")
    
    if comp.docstring:
        output.append(f"\n**Documentation**:\n{comp.docstring}\n")
    
    if comp.imports:
        unique_imports = sorted(set(comp.imports))[:5]
        output.append(f"\n**Key imports**: {', '.join(f'`{i}`' for i in unique_imports)}")
    
    return "\n".join(output)


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
