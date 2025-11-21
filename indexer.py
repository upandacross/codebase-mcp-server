"""
Code indexer for Python, SQL, and Markdown files.
Parses Python files, SQL, templates, and documentation to build a searchable index.
"""

import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class CodeComponent:
    """Represents a searchable code component."""
    type: str  # 'function', 'class', 'route', 'model', 'table', 'file'
    name: str
    filepath: str
    line_start: int
    line_end: int
    docstring: str = ""
    signature: str = ""
    decorators: List[str] = None
    parent_class: str = ""
    imports: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.decorators is None:
            self.decorators = []
        if self.imports is None:
            self.imports = []
        if self.metadata is None:
            self.metadata = {}


class CodebaseIndexer:
    """Index the codebase for fast searching."""
    
    EXCLUDE_DIRS = {
        '.venv', 'venv', '__pycache__', '.git', '.pytest_cache',
        'node_modules', '.ipynb_checkpoints', 'instance', '.data_versions'
    }
    
    EXCLUDE_PATTERNS = {
        '*.pyc', '*.pyo', '*.so', '*.dylib', '.DS_Store', '*.egg-info'
    }
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.components: List[CodeComponent] = []
        self.files_indexed: Set[str] = set()
        self.routes: Dict[str, CodeComponent] = {}
        self.models: Dict[str, CodeComponent] = {}
        self.tables: Dict[str, CodeComponent] = {}
        self.functions: Dict[str, List[CodeComponent]] = {}
        self.classes: Dict[str, CodeComponent] = {}
        
    def should_index_path(self, path: Path) -> bool:
        """Check if a path should be indexed."""
        # Check if any parent is in exclude dirs
        for parent in path.parents:
            if parent.name in self.EXCLUDE_DIRS:
                return False
        
        # Check exclude patterns
        for pattern in self.EXCLUDE_PATTERNS:
            if path.match(pattern):
                return False
        
        return True
    
    def index_codebase(self) -> Dict[str, Any]:
        """Index the entire codebase."""
        print(f"🔍 Indexing codebase at {self.project_root}")
        start_time = datetime.now()
        
        # Index Python files
        python_files = [
            f for f in self.project_root.rglob('*.py')
            if self.should_index_path(f)
        ]
        
        print(f"   Found {len(python_files)} Python files")
        for py_file in python_files:
            self._index_python_file(py_file)
        
        # Index SQL files
        sql_files = [
            f for f in self.project_root.rglob('*.sql')
            if self.should_index_path(f)
        ]
        
        print(f"   Found {len(sql_files)} SQL files")
        for sql_file in sql_files:
            self._index_sql_file(sql_file)
        
        # Index Markdown documentation
        md_files = [
            f for f in self.project_root.rglob('*.md')
            if self.should_index_path(f) and not f.name.startswith('.')
        ]
        
        print(f"   Found {len(md_files)} Markdown files")
        for md_file in md_files:
            self._index_markdown_file(md_file)
        
        # Build lookup tables
        self._build_lookup_tables()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        stats = {
            'total_components': len(self.components),
            'files_indexed': len(self.files_indexed),
            'routes': len(self.routes),
            'models': len(self.models),
            'tables': len(self.tables),
            'functions': sum(len(funcs) for funcs in self.functions.values()),
            'classes': len(self.classes),
            'elapsed_seconds': elapsed
        }
        
        print(f"✅ Indexed {stats['total_components']} components in {elapsed:.2f}s")
        return stats
    
    def _index_python_file(self, filepath: Path):
        """Index a Python file."""
        try:
            content = filepath.read_text(encoding='utf-8')
            tree = ast.parse(content, filename=str(filepath))
            
            rel_path = str(filepath.relative_to(self.project_root))
            self.files_indexed.add(rel_path)
            
            # Extract imports
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend([alias.name for alias in node.names])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            
            # Add file-level component
            file_component = CodeComponent(
                type='file',
                name=filepath.name,
                filepath=rel_path,
                line_start=1,
                line_end=len(content.splitlines()),
                docstring=ast.get_docstring(tree) or "",
                imports=imports,
                metadata={'language': 'python', 'size': len(content)}
            )
            self.components.append(file_component)
            
            # Parse classes and functions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self._index_class(node, rel_path, imports)
                elif isinstance(node, ast.FunctionDef):
                    self._index_function(node, rel_path, imports)
                    
        except Exception as e:
            print(f"   ⚠️  Error indexing {filepath}: {e}")
    
    def _index_class(self, node: ast.ClassDef, filepath: str, imports: List[str]):
        """Index a class definition."""
        decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]
        
        component = CodeComponent(
            type='class',
            name=node.name,
            filepath=filepath,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node) or "",
            decorators=decorators,
            imports=imports,
            metadata={'bases': [self._get_name(base) for base in node.bases]}
        )
        self.components.append(component)
        
        # Index methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self._index_function(item, filepath, imports, parent_class=node.name)
    
    def _index_function(self, node: ast.FunctionDef, filepath: str, 
                       imports: List[str], parent_class: str = ""):
        """Index a function definition."""
        decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]
        
        # Build signature
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        signature = f"{node.name}({', '.join(args)})"
        
        # Check if it's a Flask route
        is_route = any('route' in dec.lower() for dec in decorators)
        route_path = self._extract_route_path(node)
        
        component = CodeComponent(
            type='route' if is_route else 'function',
            name=node.name,
            filepath=filepath,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node) or "",
            signature=signature,
            decorators=decorators,
            parent_class=parent_class,
            imports=imports,
            metadata={'route_path': route_path} if route_path else {}
        )
        self.components.append(component)
    
    def _extract_route_path(self, node: ast.FunctionDef) -> str:
        """Extract the route path from Flask decorators."""
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call):
                if hasattr(dec.func, 'attr') and dec.func.attr == 'route':
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        return dec.args[0].value
        return ""
    
    def _get_decorator_name(self, node) -> str:
        """Get decorator name as string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return str(node)
    
    def _get_name(self, node) -> str:
        """Get name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return str(node)
    
    def _index_sql_file(self, filepath: Path):
        """Index a SQL file, extracting table names and structure."""
        try:
            content = filepath.read_text(encoding='utf-8')
            rel_path = str(filepath.relative_to(self.project_root))
            self.files_indexed.add(rel_path)
            
            # Add file component with content for search
            file_component = CodeComponent(
                type='file',
                name=filepath.name,
                filepath=rel_path,
                line_start=1,
                line_end=len(content.splitlines()),
                docstring=content[:500],  # First 500 chars as preview
                metadata={'language': 'sql', 'size': len(content), 'content': content}
            )
            self.components.append(file_component)
            
            # Extract table names from CREATE TABLE statements
            create_table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z_][a-z0-9_]*)'
            for match in re.finditer(create_table_pattern, content, re.IGNORECASE):
                table_name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1
                
                # Find the end of the CREATE TABLE statement
                end_pos = content.find(';', match.start())
                if end_pos == -1:
                    end_pos = len(content)
                end_line = content[:end_pos].count('\n') + 1
                
                component = CodeComponent(
                    type='table',
                    name=table_name,
                    filepath=rel_path,
                    line_start=line_num,
                    line_end=end_line,
                    metadata={'language': 'sql'}
                )
                self.components.append(component)
                
        except Exception as e:
            print(f"   ⚠️  Error indexing {filepath}: {e}")
    
    def _index_markdown_file(self, filepath: Path):
        """Index a Markdown documentation file."""
        try:
            content = filepath.read_text(encoding='utf-8')
            rel_path = str(filepath.relative_to(self.project_root))
            self.files_indexed.add(rel_path)
            
            # Extract title (first # heading)
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else filepath.stem
            
            # Extract first paragraph as summary
            lines = content.split('\n')
            summary_lines = []
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    summary_lines.append(line.strip())
                    if len(summary_lines) >= 3:
                        break
            summary = ' '.join(summary_lines)[:200]
            
            component = CodeComponent(
                type='file',
                name=filepath.name,
                filepath=rel_path,
                line_start=1,
                line_end=len(lines),
                docstring=summary,
                metadata={
                    'language': 'markdown',
                    'title': title,
                    'size': len(content),
                    'content': content  # Store full content for search
                }
            )
            self.components.append(component)
            
        except Exception as e:
            print(f"   ⚠️  Error indexing {filepath}: {e}")
    
    def _build_lookup_tables(self):
        """Build fast lookup dictionaries."""
        for comp in self.components:
            if comp.type == 'route':
                route_path = comp.metadata.get('route_path', comp.name)
                self.routes[route_path] = comp
            elif comp.type == 'model' or (comp.type == 'class' and 
                                          any('Model' in base for base in comp.metadata.get('bases', []))):
                self.models[comp.name] = comp
                comp.type = 'model'  # Update type
            elif comp.type == 'table':
                self.tables[comp.name] = comp
            elif comp.type == 'function':
                if comp.name not in self.functions:
                    self.functions[comp.name] = []
                self.functions[comp.name].append(comp)
            elif comp.type == 'class':
                self.classes[comp.name] = comp
    
    def search(self, query: str, component_type: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Search the codebase."""
        query_lower = query.lower()
        results = []
        
        for comp in self.components:
            if component_type and comp.type != component_type:
                continue
            
            score = 0
            
            # Exact name match
            if query_lower == comp.name.lower():
                score += 100
            # Name contains query
            elif query_lower in comp.name.lower():
                score += 50
            # Docstring contains query
            elif query_lower in comp.docstring.lower():
                score += 20
            # Filepath contains query
            elif query_lower in comp.filepath.lower():
                score += 10
            # For markdown files, search title and content
            elif comp.metadata and comp.metadata.get('language') == 'markdown':
                if query_lower in comp.metadata.get('title', '').lower():
                    score += 30
                elif query_lower in comp.metadata.get('content', '').lower():
                    score += 15
            # For SQL files, search content
            elif comp.metadata and comp.metadata.get('language') == 'sql':
                if query_lower in comp.metadata.get('content', '').lower():
                    score += 15
            
            if score > 0:
                result = asdict(comp)
                result['score'] = score
                results.append(result)
        
        # Sort by score descending
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]
    
    def save_index(self, output_path: Path):
        """Save the index to a JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'indexed_at': datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'components': [asdict(comp) for comp in self.components],
            'stats': {
                'total_components': len(self.components),
                'files_indexed': len(self.files_indexed),
                'routes': len(self.routes),
                'models': len(self.models),
                'tables': len(self.tables),
                'functions': sum(len(funcs) for funcs in self.functions.values()),
                'classes': len(self.classes)
            }
        }
        
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Saved index to {output_path}")
    
    @classmethod
    def load_index(cls, index_path: Path, project_root: Path) -> 'CodebaseIndexer':
        """Load an index from a JSON file."""
        with index_path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        
        indexer = cls(project_root)
        indexer.components = [
            CodeComponent(**comp) for comp in data['components']
        ]
        indexer._build_lookup_tables()
        
        print(f"📂 Loaded index from {index_path}")
        print(f"   {data['stats']['total_components']} components indexed")
        return indexer


def main():
    """CLI for building the index."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Index a codebase for MCP server access')
    parser.add_argument('--project-root', type=Path, default=Path(__file__).parent.parent.parent,
                       help='Project root directory')
    parser.add_argument('--output', type=Path, 
                       default=Path(__file__).parent / 'codebase_index.json',
                       help='Output JSON file')
    parser.add_argument('--search', type=str, help='Search after indexing')
    
    args = parser.parse_args()
    
    indexer = CodebaseIndexer(args.project_root)
    indexer.index_codebase()
    indexer.save_index(args.output)
    
    if args.search:
        print(f"\n🔎 Searching for: {args.search}")
        results = indexer.search(args.search, limit=10)
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['type']}: {result['name']}")
            print(f"   📄 {result['filepath']}:{result['line_start']}")
            if result['docstring']:
                print(f"   📝 {result['docstring'][:80]}...")


if __name__ == '__main__':
    main()
