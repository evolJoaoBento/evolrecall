#!/usr/bin/env python3
"""
Documentation MCP Server - Property-Based Schema
MCP server for managing unified property-based documentation database
Compatible with Claude Desktop
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
import sys
import asyncio
import os
import ast
from typing import Optional, Dict, List, Any

# MCP SDK imports
try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    import mcp.server.stdio
    import mcp.types as types
except ImportError:
    print("Installing MCP SDK...", file=sys.stderr)
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mcp"])
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    import mcp.server.stdio
    import mcp.types as types


class DocumentationMCP:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.server = Server("documentation-mcp")
        self.init_database()
        self.setup_handlers()
    
    def init_database(self):
        """Initialize the property-based documentation database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # Create PROJECTS table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    name TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(slug)")
            
            # Create TAGS table (hierarchical)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    parent_tag_id TEXT,
                    project_id TEXT,
                    color TEXT,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    UNIQUE(slug, parent_tag_id, project_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_hierarchy ON tags(slug, parent_tag_id, project_id)")
            
            # Create PROPERTIES table (core hierarchical data)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS properties (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    key TEXT NOT NULL,
                    value TEXT,
                    type TEXT DEFAULT 'text',
                    parent_id TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_id) REFERENCES properties(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_properties_key_parent ON properties(key, parent_id, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_properties_parent ON properties(parent_id)")
            
            # Create PROPERTY_TAGS junction table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS property_tags (
                    property_id TEXT NOT NULL,
                    tag_id TEXT NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (property_id, tag_id),
                    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                )
            """)
            
            # Create VERSIONS table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS versions (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    property_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    value_snapshot TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_versions_property ON versions(property_id, version_number)")
            
            # Create SEARCH_INDEX table for full-text search
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_index (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    property_id TEXT UNIQUE NOT NULL,
                    search_vector TEXT,
                    computed_path TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
                )
            """)
            
            # Create default project if none exists
            cursor.execute("SELECT COUNT(*) FROM projects")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO projects (name, slug) 
                    VALUES ('Default', 'default')
                """)
            
            # Create default tags
            cursor.execute("SELECT COUNT(*) FROM tags")
            if cursor.fetchone()[0] == 0:
                default_project_id = cursor.execute("SELECT id FROM projects WHERE slug = 'default'").fetchone()[0]
                default_tags = [
                    ('Documentation', 'documentation'),
                    ('Code', 'code'),
                    ('API', 'api'),
                    ('Configuration', 'config'),
                    ('Notes', 'notes')
                ]
                for name, slug in default_tags:
                    cursor.execute("""
                        INSERT INTO tags (name, slug, project_id) 
                        VALUES (?, ?, ?)
                    """, (name, slug, default_project_id))
            
            conn.commit()
    
    def setup_handlers(self):
        """Setup MCP request handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """List available tools"""
            return [
                # Property management
                types.Tool(
                    name="create_property",
                    description="Create a new property with hierarchical support",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "Property key (slug-formatted)"},
                            "value": {"type": "string", "description": "Property value"},
                            "type": {"type": "string", "enum": ["text", "json", "number", "boolean", "markdown"], "default": "text"},
                            "parent_key": {"type": "string", "description": "Parent property key (optional)"},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Tag slugs to assign"}
                        },
                        "required": ["key", "value"]
                    }
                ),
                types.Tool(
                    name="search_properties",
                    description="Search properties by key, value, or tags",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tag slugs"},
                            "type": {"type": "string", "description": "Filter by property type"},
                            "limit": {"type": "integer", "default": 20}
                        }
                    }
                ),
                types.Tool(
                    name="get_property_tree",
                    description="Get property hierarchy starting from a key",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "Root property key"},
                            "depth": {"type": "integer", "default": 3, "description": "Maximum depth to traverse"}
                        },
                        "required": ["key"]
                    }
                ),
                # Tag management
                types.Tool(
                    name="create_tag",
                    description="Create a new tag with optional hierarchy",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Tag display name"},
                            "slug": {"type": "string", "description": "Tag slug (auto-generated if not provided)"},
                            "parent_tag": {"type": "string", "description": "Parent tag slug"},
                            "project": {"type": "string", "description": "Project slug", "default": "default"},
                            "color": {"type": "string", "description": "Color for UI"}
                        },
                        "required": ["name"]
                    }
                ),
                types.Tool(
                    name="get_tag_tree",
                    description="Get tag hierarchy for a project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "default": "default"},
                            "parent_tag": {"type": "string", "description": "Start from specific parent tag"}
                        }
                    }
                ),
                # Code scanning
                types.Tool(
                    name="scan_codebase",
                    description="Scan codebase and store as hierarchical properties",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "directory": {"type": "string", "description": "Directory to scan"},
                            "extensions": {"type": "array", "items": {"type": "string"}, "default": [".py"]},
                            "project": {"type": "string", "default": "default"}
                        },
                        "required": ["directory"]
                    }
                ),
                # Documentation management  
                types.Tool(
                    name="add_documentation",
                    description="Add documentation as structured properties",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Documentation title"},
                            "content": {"type": "string", "description": "Documentation content"},
                            "section": {"type": "string", "description": "Section/category"},
                            "project": {"type": "string", "default": "default"},
                            "tags": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["title", "content"]
                    }
                ),
                # Activity summaries
                types.Tool(
                    name="add_activity_summary",
                    description="Add daily activity summary",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                            "summary": {"type": "string", "description": "Activity summary"},
                            "insights": {"type": "string", "description": "Key insights"},
                            "project": {"type": "string", "default": "default"}
                        },
                        "required": ["date", "summary"]
                    }
                ),
                types.Tool(
                    name="get_activity_summaries",
                    description="Get activity summaries with date range",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                            "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                            "project": {"type": "string", "default": "default"},
                            "limit": {"type": "integer", "default": 30}
                        }
                    }
                ),
                # Database utilities
                types.Tool(
                    name="get_database_stats",
                    description="Get comprehensive database statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                types.Tool(
                    name="rebuild_search_index",
                    description="Rebuild the full-text search index",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            """Handle tool calls"""
            
            method_map = {
                "create_property": self.create_property,
                "search_properties": self.search_properties,
                "get_property_tree": self.get_property_tree,
                "create_tag": self.create_tag,
                "get_tag_tree": self.get_tag_tree,
                "scan_codebase": self.scan_codebase,
                "add_documentation": self.add_documentation,
                "add_activity_summary": self.add_activity_summary,
                "get_activity_summaries": self.get_activity_summaries,
                "get_database_stats": self.get_database_stats,
                "rebuild_search_index": self.rebuild_search_index
            }
            
            if name in method_map:
                result = await method_map[name](arguments)
            else:
                result = {"error": f"Unknown tool: {name}"}
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )]
    
    def _slugify(self, text: str) -> str:
        """Convert text to slug format"""
        import re
        return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    
    def _get_project_id(self, project_slug: str) -> Optional[str]:
        """Get project ID by slug"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM projects WHERE slug = ?", (project_slug,))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def _get_tag_id(self, tag_slug: str, project_id: str = None) -> Optional[str]:
        """Get tag ID by slug"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if project_id:
                cursor.execute("SELECT id FROM tags WHERE slug = ? AND project_id = ?", (tag_slug, project_id))
            else:
                cursor.execute("SELECT id FROM tags WHERE slug = ?", (tag_slug,))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def _update_search_index(self, property_id: str):
        """Update search index for a property"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get property details
            cursor.execute("""
                SELECT key, value, type FROM properties 
                WHERE id = ? AND status = 'active'
            """, (property_id,))
            prop = cursor.fetchone()
            
            if not prop:
                return
            
            key, value, prop_type = prop
            
            # Build search vector
            search_text_parts = [key]
            if value:
                search_text_parts.append(value)
            
            # Get computed path
            path_parts = []
            current_id = property_id
            while current_id:
                cursor.execute("SELECT key, parent_id FROM properties WHERE id = ?", (current_id,))
                row = cursor.fetchone()
                if row:
                    path_parts.append(row[0])
                    current_id = row[1]
                else:
                    break
            
            computed_path = " / ".join(reversed(path_parts))
            search_vector = " ".join(search_text_parts)
            
            # Update search index
            cursor.execute("""
                INSERT OR REPLACE INTO search_index 
                (property_id, search_vector, computed_path, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (property_id, search_vector, computed_path))
            
            conn.commit()
    
    async def create_property(self, args: dict) -> dict:
        """Create a new property"""
        try:
            key = args.get("key")
            value = args.get("value")
            prop_type = args.get("type", "text")
            parent_key = args.get("parent_key")
            tags = args.get("tags", [])
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get parent ID if specified
                parent_id = None
                if parent_key:
                    cursor.execute("SELECT id FROM properties WHERE key = ? AND status = 'active'", (parent_key,))
                    row = cursor.fetchone()
                    if row:
                        parent_id = row[0]
                    else:
                        return {"error": f"Parent property '{parent_key}' not found"}
                
                # Create property
                property_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO properties (id, key, value, type, parent_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (property_id, key, value, prop_type, parent_id))
                
                # Create version
                cursor.execute("""
                    INSERT INTO versions (property_id, version_number, value_snapshot)
                    VALUES (?, 1, ?)
                """, (property_id, value))
                
                # Assign tags
                default_project_id = self._get_project_id("default")
                for tag_slug in tags:
                    tag_id = self._get_tag_id(tag_slug, default_project_id)
                    if tag_id:
                        cursor.execute("""
                            INSERT OR IGNORE INTO property_tags (property_id, tag_id)
                            VALUES (?, ?)
                        """, (property_id, tag_id))
                
                conn.commit()
                
                # Update search index
                self._update_search_index(property_id)
                
                return {
                    "success": True,
                    "property_id": property_id,
                    "key": key,
                    "message": f"Property '{key}' created successfully"
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def search_properties(self, args: dict) -> dict:
        """Search properties"""
        try:
            query = args.get("query", "")
            tag_filters = args.get("tags", [])
            type_filter = args.get("type")
            limit = args.get("limit", 20)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build search query
                sql = """
                    SELECT DISTINCT p.id, p.key, p.value, p.type, p.parent_id,
                           si.computed_path, GROUP_CONCAT(t.name) as tags
                    FROM properties p
                    LEFT JOIN search_index si ON p.id = si.property_id
                    LEFT JOIN property_tags pt ON p.id = pt.property_id
                    LEFT JOIN tags t ON pt.tag_id = t.id
                    WHERE p.status = 'active'
                """
                params = []
                
                if query:
                    sql += " AND (p.key LIKE ? OR p.value LIKE ? OR si.search_vector LIKE ?)"
                    query_param = f"%{query}%"
                    params.extend([query_param, query_param, query_param])
                
                if type_filter:
                    sql += " AND p.type = ?"
                    params.append(type_filter)
                
                if tag_filters:
                    placeholders = ",".join("?" * len(tag_filters))
                    sql += f" AND t.slug IN ({placeholders})"
                    params.extend(tag_filters)
                
                sql += " GROUP BY p.id ORDER BY p.updated_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(sql, params)
                
                properties = []
                for row in cursor.fetchall():
                    prop_id, key, value, prop_type, parent_id, path, tags_str = row
                    properties.append({
                        "id": prop_id,
                        "key": key,
                        "value": value[:200] if value else None,  # Truncate for preview
                        "type": prop_type,
                        "path": path,
                        "tags": tags_str.split(",") if tags_str else []
                    })
                
                return {
                    "query": query,
                    "total_results": len(properties),
                    "properties": properties
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def get_property_tree(self, args: dict) -> dict:
        """Get property hierarchy"""
        try:
            root_key = args.get("key")
            max_depth = args.get("depth", 3)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get root property
                cursor.execute("""
                    SELECT id, key, value, type FROM properties 
                    WHERE key = ? AND status = 'active'
                """, (root_key,))
                root = cursor.fetchone()
                
                if not root:
                    return {"error": f"Property '{root_key}' not found"}
                
                def build_tree(parent_id, current_depth):
                    if current_depth >= max_depth:
                        return []
                    
                    cursor.execute("""
                        SELECT id, key, value, type FROM properties 
                        WHERE parent_id = ? AND status = 'active'
                        ORDER BY key
                    """, (parent_id,))
                    
                    children = []
                    for row in cursor.fetchall():
                        child_id, key, value, prop_type = row
                        child = {
                            "id": child_id,
                            "key": key,
                            "value": value,
                            "type": prop_type,
                            "children": build_tree(child_id, current_depth + 1)
                        }
                        children.append(child)
                    
                    return children
                
                root_id, root_key, root_value, root_type = root
                tree = {
                    "id": root_id,
                    "key": root_key,
                    "value": root_value,
                    "type": root_type,
                    "children": build_tree(root_id, 0)
                }
                
                return {
                    "root_key": root_key,
                    "max_depth": max_depth,
                    "tree": tree
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def create_tag(self, args: dict) -> dict:
        """Create a new tag"""
        try:
            name = args.get("name")
            slug = args.get("slug") or self._slugify(name)
            parent_tag_slug = args.get("parent_tag")
            project_slug = args.get("project", "default")
            color = args.get("color")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get project ID
                project_id = self._get_project_id(project_slug)
                if not project_id:
                    return {"error": f"Project '{project_slug}' not found"}
                
                # Get parent tag ID if specified
                parent_tag_id = None
                if parent_tag_slug:
                    parent_tag_id = self._get_tag_id(parent_tag_slug, project_id)
                    if not parent_tag_id:
                        return {"error": f"Parent tag '{parent_tag_slug}' not found"}
                
                # Create tag
                tag_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO tags (id, name, slug, parent_tag_id, project_id, color)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (tag_id, name, slug, parent_tag_id, project_id, color))
                
                conn.commit()
                
                return {
                    "success": True,
                    "tag_id": tag_id,
                    "name": name,
                    "slug": slug,
                    "message": f"Tag '{name}' created successfully"
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def get_tag_tree(self, args: dict) -> dict:
        """Get tag hierarchy"""
        try:
            project_slug = args.get("project", "default")
            parent_tag_slug = args.get("parent_tag")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get project ID
                project_id = self._get_project_id(project_slug)
                if not project_id:
                    return {"error": f"Project '{project_slug}' not found"}
                
                # Get parent tag ID if specified
                parent_tag_id = None
                if parent_tag_slug:
                    parent_tag_id = self._get_tag_id(parent_tag_slug, project_id)
                    if not parent_tag_id:
                        return {"error": f"Parent tag '{parent_tag_slug}' not found"}
                
                def build_tag_tree(parent_id):
                    cursor.execute("""
                        SELECT id, name, slug, color, 
                               (SELECT COUNT(*) FROM property_tags WHERE tag_id = tags.id) as property_count
                        FROM tags 
                        WHERE parent_tag_id IS ? AND project_id = ?
                        ORDER BY sort_order, name
                    """, (parent_id, project_id))
                    
                    children = []
                    for row in cursor.fetchall():
                        tag_id, name, slug, color, prop_count = row
                        child = {
                            "id": tag_id,
                            "name": name,
                            "slug": slug,
                            "color": color,
                            "property_count": prop_count,
                            "children": build_tag_tree(tag_id)
                        }
                        children.append(child)
                    
                    return children
                
                tree = build_tag_tree(parent_tag_id)
                
                return {
                    "project": project_slug,
                    "parent_tag": parent_tag_slug,
                    "tags": tree
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def scan_codebase(self, args: dict) -> dict:
        """Scan codebase and store as properties"""
        try:
            directory = Path(args.get("directory"))
            extensions = args.get("extensions", [".py"])
            project_slug = args.get("project", "default")
            
            if not directory.exists():
                return {"error": f"Directory not found: {directory}"}
            
            project_id = self._get_project_id(project_slug)
            if not project_id:
                return {"error": f"Project '{project_slug}' not found"}
            
            code_tag_id = self._get_tag_id("code", project_id)
            
            total_files = 0
            total_items = 0
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for ext in extensions:
                    for file_path in directory.rglob(f"*{ext}"):
                        if ext == ".py":
                            # Create file property
                            file_key = f"file-{self._slugify(str(file_path.relative_to(directory)))}"
                            file_property_id = str(uuid.uuid4())
                            
                            cursor.execute("""
                                INSERT OR REPLACE INTO properties (id, key, value, type)
                                VALUES (?, ?, ?, 'file')
                            """, (file_property_id, file_key, str(file_path)))
                            
                            if code_tag_id:
                                cursor.execute("""
                                    INSERT OR IGNORE INTO property_tags (property_id, tag_id)
                                    VALUES (?, ?)
                                """, (file_property_id, code_tag_id))
                            
                            # Extract and store code items
                            items = self._extract_python_docs(file_path)
                            for item in items:
                                item_key = f"{file_key}-{item['name']}"
                                item_property_id = str(uuid.uuid4())
                                
                                # Create structured value
                                item_data = {
                                    "signature": item.get("signature"),
                                    "docstring": item.get("docstring"),
                                    "line": item.get("line"),
                                    "type": item["type"]
                                }
                                
                                cursor.execute("""
                                    INSERT OR REPLACE INTO properties 
                                    (id, key, value, type, parent_id)
                                    VALUES (?, ?, ?, 'code_item', ?)
                                """, (item_property_id, item_key, json.dumps(item_data), file_property_id))
                                
                                if code_tag_id:
                                    cursor.execute("""
                                        INSERT OR IGNORE INTO property_tags (property_id, tag_id)
                                        VALUES (?, ?)
                                    """, (item_property_id, code_tag_id))
                                
                                self._update_search_index(item_property_id)
                                total_items += 1
                            
                            self._update_search_index(file_property_id)
                            total_files += 1
                
                conn.commit()
            
            return {
                "success": True,
                "files_scanned": total_files,
                "items_extracted": total_items,
                "directory": str(directory)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _extract_python_docs(self, file_path: Path) -> list:
        """Extract documentation from Python file"""
        items = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    items.append({
                        "type": "function",
                        "name": node.name,
                        "signature": self._get_function_signature(node),
                        "docstring": ast.get_docstring(node),
                        "line": node.lineno
                    })
                elif isinstance(node, ast.ClassDef):
                    items.append({
                        "type": "class", 
                        "name": node.name,
                        "signature": f"class {node.name}",
                        "docstring": ast.get_docstring(node),
                        "line": node.lineno
                    })
                    # Extract methods
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            items.append({
                                "type": "method",
                                "name": f"{node.name}.{item.name}",
                                "signature": self._get_function_signature(item),
                                "docstring": ast.get_docstring(item),
                                "line": item.lineno
                            })
        except:
            pass  # Ignore files that can't be parsed
        
        return items
    
    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature"""
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        return f"{node.name}({', '.join(args)})"
    
    async def add_documentation(self, args: dict) -> dict:
        """Add documentation as structured properties"""
        try:
            title = args.get("title")
            content = args.get("content")
            section = args.get("section", "general")
            project_slug = args.get("project", "default")
            tags = args.get("tags", [])
            
            project_id = self._get_project_id(project_slug)
            if not project_id:
                return {"error": f"Project '{project_slug}' not found"}
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create or get section property
                section_key = f"docs-{self._slugify(section)}"
                cursor.execute("""
                    SELECT id FROM properties WHERE key = ? AND status = 'active'
                """, (section_key,))
                row = cursor.fetchone()
                
                if row:
                    section_id = row[0]
                else:
                    section_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO properties (id, key, value, type)
                        VALUES (?, ?, ?, 'section')
                    """, (section_id, section_key, section))
                
                # Create document property
                doc_key = f"{section_key}-{self._slugify(title)}"
                doc_property_id = str(uuid.uuid4())
                
                cursor.execute("""
                    INSERT INTO properties (id, key, value, type, parent_id)
                    VALUES (?, ?, ?, 'documentation', ?)
                """, (doc_property_id, doc_key, content, section_id))
                
                # Assign tags
                doc_tag_id = self._get_tag_id("documentation", project_id)
                if doc_tag_id:
                    cursor.execute("""
                        INSERT OR IGNORE INTO property_tags (property_id, tag_id)
                        VALUES (?, ?)
                    """, (doc_property_id, doc_tag_id))
                
                for tag_slug in tags:
                    tag_id = self._get_tag_id(tag_slug, project_id)
                    if tag_id:
                        cursor.execute("""
                            INSERT OR IGNORE INTO property_tags (property_id, tag_id)
                            VALUES (?, ?)
                        """, (doc_property_id, tag_id))
                
                conn.commit()
                
                self._update_search_index(doc_property_id)
                
                return {
                    "success": True,
                    "property_id": doc_property_id,
                    "key": doc_key,
                    "message": f"Documentation '{title}' added successfully"
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def add_activity_summary(self, args: dict) -> dict:
        """Add daily activity summary"""
        try:
            date = args.get("date")
            summary = args.get("summary")
            insights = args.get("insights", "")
            project_slug = args.get("project", "default")
            
            project_id = self._get_project_id(project_slug)
            if not project_id:
                return {"error": f"Project '{project_slug}' not found"}
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create or get summaries section
                summaries_key = "activity-summaries"
                cursor.execute("""
                    SELECT id FROM properties WHERE key = ? AND status = 'active'
                """, (summaries_key,))
                row = cursor.fetchone()
                
                if row:
                    summaries_id = row[0]
                else:
                    summaries_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO properties (id, key, value, type)
                        VALUES (?, ?, ?, 'section')
                    """, (summaries_id, summaries_key, "Activity Summaries"))
                
                # Create summary property
                summary_key = f"summary-{date}"
                summary_property_id = str(uuid.uuid4())
                
                summary_data = {
                    "date": date,
                    "summary": summary,
                    "insights": insights
                }
                
                cursor.execute("""
                    INSERT OR REPLACE INTO properties (id, key, value, type, parent_id)
                    VALUES (?, ?, ?, 'activity_summary', ?)
                """, (summary_property_id, summary_key, json.dumps(summary_data), summaries_id))
                
                # Tag as notes
                notes_tag_id = self._get_tag_id("notes", project_id)
                if notes_tag_id:
                    cursor.execute("""
                        INSERT OR IGNORE INTO property_tags (property_id, tag_id)
                        VALUES (?, ?)
                    """, (summary_property_id, notes_tag_id))
                
                conn.commit()
                self._update_search_index(summary_property_id)
                
                return {
                    "success": True,
                    "property_id": summary_property_id,
                    "date": date,
                    "message": f"Activity summary for {date} added successfully"
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def get_activity_summaries(self, args: dict) -> dict:
        """Get activity summaries with date range"""
        try:
            start_date = args.get("start_date")
            end_date = args.get("end_date")
            project_slug = args.get("project", "default")
            limit = args.get("limit", 30)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                sql = """
                    SELECT p.key, p.value, p.updated_at
                    FROM properties p
                    WHERE p.type = 'activity_summary' AND p.status = 'active'
                """
                params = []
                
                if start_date:
                    sql += " AND p.key >= ?"
                    params.append(f"summary-{start_date}")
                    
                if end_date:
                    sql += " AND p.key <= ?"
                    params.append(f"summary-{end_date}")
                
                sql += " ORDER BY p.key DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(sql, params)
                
                summaries = []
                for row in cursor.fetchall():
                    key, value_json, updated_at = row
                    try:
                        data = json.loads(value_json) if value_json else {}
                        summaries.append({
                            "key": key,
                            "date": data.get("date"),
                            "summary": data.get("summary"),
                            "insights": data.get("insights"),
                            "updated_at": updated_at
                        })
                    except:
                        continue
                
                return {
                    "summaries": summaries,
                    "total": len(summaries),
                    "date_range": {
                        "start": start_date,
                        "end": end_date
                    }
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def get_database_stats(self) -> dict:
        """Get comprehensive database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Properties stats
                cursor.execute("SELECT COUNT(*) FROM properties WHERE status = 'active'")
                total_properties = cursor.fetchone()[0]
                
                cursor.execute("SELECT type, COUNT(*) FROM properties WHERE status = 'active' GROUP BY type")
                properties_by_type = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Tags stats
                cursor.execute("SELECT COUNT(*) FROM tags")
                total_tags = cursor.fetchone()[0]
                
                # Projects stats
                cursor.execute("SELECT COUNT(*) FROM projects WHERE is_active = 1")
                active_projects = cursor.fetchone()[0]
                
                # Versions stats
                cursor.execute("SELECT COUNT(*) FROM versions")
                total_versions = cursor.fetchone()[0]
                
                # Search index stats
                cursor.execute("SELECT COUNT(*) FROM search_index")
                indexed_properties = cursor.fetchone()[0]
                
                # Recent activity
                cursor.execute("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM properties 
                    WHERE created_at >= datetime('now', '-30 days')
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                    LIMIT 10
                """)
                recent_activity = [{"date": row[0], "count": row[1]} for row in cursor.fetchall()]
                
                return {
                    "database_path": self.db_path,
                    "total_properties": total_properties,
                    "properties_by_type": properties_by_type,
                    "total_tags": total_tags,
                    "active_projects": active_projects,
                    "total_versions": total_versions,
                    "indexed_properties": indexed_properties,
                    "index_coverage": round(indexed_properties / max(total_properties, 1) * 100, 1),
                    "recent_activity": recent_activity,
                    "size_mb": round(Path(self.db_path).stat().st_size / 1024 / 1024, 2)
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def rebuild_search_index(self, args: dict) -> dict:
        """Rebuild the full-text search index"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clear existing index
                cursor.execute("DELETE FROM search_index")
                
                # Get all active properties
                cursor.execute("SELECT id FROM properties WHERE status = 'active'")
                property_ids = [row[0] for row in cursor.fetchall()]
                
                # Rebuild index for each property
                for property_id in property_ids:
                    self._update_search_index(property_id)
                
                conn.commit()
                
                return {
                    "success": True,
                    "indexed_properties": len(property_ids),
                    "message": "Search index rebuilt successfully"
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def run(self):
        """Run the MCP server"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="documentation-mcp",
                    server_version="2.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Documentation MCP Server - Property-Based Schema")
    parser.add_argument("--db-path", required=True, help="Path to documentation database")
    
    args = parser.parse_args()
    
    server = DocumentationMCP(args.db_path)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()