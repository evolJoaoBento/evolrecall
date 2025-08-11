#!/usr/bin/env python3
"""
OpenRecall MCP Server
MCP server for querying OpenRecall activity database
Compatible with Claude Desktop
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys
import asyncio

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


class OpenRecallMCP:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.server = Server("openrecall-mcp")
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup MCP request handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """List available tools"""
            return [
                types.Tool(
                    name="query_activities",
                    description="Query OpenRecall activities with filters",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "time_range": {
                                "type": "string",
                                "description": "Time range: today, yesterday, week, month, or all",
                                "enum": ["today", "yesterday", "week", "month", "all"]
                            },
                            "app_filter": {
                                "type": "string",
                                "description": "Filter by app name (optional)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max results to return",
                                "default": 20
                            }
                        }
                    }
                ),
                types.Tool(
                    name="get_app_statistics",
                    description="Get statistics for app usage",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "time_range": {
                                "type": "string",
                                "enum": ["today", "yesterday", "week", "month", "all"]
                            }
                        },
                        "required": ["time_range"]
                    }
                ),
                types.Tool(
                    name="find_focus_sessions",
                    description="Find continuous work sessions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "min_duration": {
                                "type": "integer",
                                "description": "Minimum session duration in minutes",
                                "default": 30
                            },
                            "days_back": {
                                "type": "integer",
                                "description": "Days to look back",
                                "default": 7
                            }
                        }
                    }
                ),
                types.Tool(
                    name="get_productivity_insights",
                    description="Get productivity analysis and insights",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "Date to analyze (YYYY-MM-DD) or 'latest'"
                            }
                        },
                        "required": ["date"]
                    }
                ),
                types.Tool(
                    name="search_activities",
                    description="Search activities by title keyword",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "keyword": {
                                "type": "string",
                                "description": "Keyword to search in titles"
                            },
                            "limit": {
                                "type": "integer",
                                "default": 20
                            }
                        },
                        "required": ["keyword"]
                    }
                ),
                types.Tool(
                    name="get_database_info",
                    description="Get information about the database",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict
        ) -> list[types.TextContent]:
            """Handle tool calls"""
            
            if name == "query_activities":
                result = await self.query_activities(arguments)
            elif name == "get_app_statistics":
                result = await self.get_app_statistics(arguments)
            elif name == "find_focus_sessions":
                result = await self.find_focus_sessions(arguments)
            elif name == "get_productivity_insights":
                result = await self.get_productivity_insights(arguments)
            elif name == "search_activities":
                result = await self.search_activities(arguments)
            elif name == "get_database_info":
                result = await self.get_database_info()
            else:
                result = {"error": f"Unknown tool: {name}"}
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )]
    
    async def query_activities(self, args: dict) -> dict:
        """Query activities from database"""
        try:
            time_range = args.get("time_range", "week")
            app_filter = args.get("app_filter")
            limit = args.get("limit", 20)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get time boundaries
                cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM entries")
                min_ts, max_ts = cursor.fetchone()
                
                if not min_ts or not max_ts:
                    return {"error": "No data in database"}
                
                # Calculate time filter
                if time_range == "today":
                    start_ts = int(datetime.fromtimestamp(max_ts).replace(hour=0, minute=0, second=0).timestamp())
                elif time_range == "yesterday":
                    yesterday = datetime.fromtimestamp(max_ts).replace(hour=0, minute=0, second=0) - timedelta(days=1)
                    start_ts = int(yesterday.timestamp())
                elif time_range == "week":
                    start_ts = max_ts - (7 * 86400)
                elif time_range == "month":
                    start_ts = max_ts - (30 * 86400)
                else:
                    start_ts = min_ts
                
                # Build query
                query = """
                    SELECT app, title, COUNT(*) as count,
                           MIN(timestamp) as first_seen,
                           MAX(timestamp) as last_seen
                    FROM entries
                    WHERE timestamp >= ?
                """
                params = [start_ts]
                
                if app_filter:
                    query += " AND app LIKE ?"
                    params.append(f"%{app_filter}%")
                
                query += " GROUP BY app, title ORDER BY count DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                
                activities = []
                for row in cursor.fetchall():
                    app, title, count, first_ts, last_ts = row
                    activities.append({
                        "app": app,
                        "title": title[:100],  # Truncate long titles
                        "count": count,
                        "first_seen": datetime.fromtimestamp(first_ts).isoformat(),
                        "last_seen": datetime.fromtimestamp(last_ts).isoformat(),
                        "duration_minutes": round((last_ts - first_ts) / 60, 1)
                    })
                
                return {
                    "time_range": time_range,
                    "total_results": len(activities),
                    "activities": activities
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def get_app_statistics(self, args: dict) -> dict:
        """Get app usage statistics"""
        try:
            time_range = args.get("time_range", "week")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get time boundaries
                cursor.execute("SELECT MAX(timestamp) FROM entries")
                max_ts = cursor.fetchone()[0]
                if not max_ts:
                    return {"error": "No data"}
                
                # Calculate time filter
                if time_range == "today":
                    start_ts = int(datetime.fromtimestamp(max_ts).replace(hour=0, minute=0, second=0).timestamp())
                elif time_range == "yesterday":
                    yesterday = datetime.fromtimestamp(max_ts).replace(hour=0, minute=0, second=0) - timedelta(days=1)
                    start_ts = int(yesterday.timestamp())
                    max_ts = int(datetime.fromtimestamp(max_ts).replace(hour=0, minute=0, second=0).timestamp())
                elif time_range == "week":
                    start_ts = max_ts - (7 * 86400)
                elif time_range == "month":
                    start_ts = max_ts - (30 * 86400)
                else:
                    cursor.execute("SELECT MIN(timestamp) FROM entries")
                    start_ts = cursor.fetchone()[0]
                
                # Get app statistics
                cursor.execute("""
                    SELECT app,
                           COUNT(*) as total_entries,
                           COUNT(DISTINCT DATE(datetime(timestamp, 'unixepoch'))) as days_used,
                           MIN(timestamp) as first_use,
                           MAX(timestamp) as last_use
                    FROM entries
                    WHERE timestamp BETWEEN ? AND ?
                    GROUP BY app
                    ORDER BY total_entries DESC
                """, (start_ts, max_ts))
                
                apps = []
                for row in cursor.fetchall():
                    app, entries, days, first, last = row
                    apps.append({
                        "app": app,
                        "total_entries": entries,
                        "days_used": days,
                        "avg_entries_per_day": round(entries / max(days, 1), 1),
                        "first_use": datetime.fromtimestamp(first).isoformat(),
                        "last_use": datetime.fromtimestamp(last).isoformat(),
                        "total_hours": round((last - first) / 3600, 1)
                    })
                
                return {
                    "time_range": time_range,
                    "period": {
                        "start": datetime.fromtimestamp(start_ts).isoformat(),
                        "end": datetime.fromtimestamp(max_ts).isoformat()
                    },
                    "total_apps": len(apps),
                    "apps": apps
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def find_focus_sessions(self, args: dict) -> dict:
        """Find focused work sessions"""
        try:
            min_duration = args.get("min_duration", 30)
            days_back = args.get("days_back", 7)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get recent entries
                cursor.execute("SELECT MAX(timestamp) FROM entries")
                max_ts = cursor.fetchone()[0]
                if not max_ts:
                    return {"error": "No data"}
                
                start_ts = max_ts - (days_back * 86400)
                
                cursor.execute("""
                    SELECT app, title, timestamp
                    FROM entries
                    WHERE timestamp > ?
                    ORDER BY timestamp
                """, (start_ts,))
                
                # Identify sessions
                sessions = []
                current_session = None
                last_ts = None
                
                for row in cursor.fetchall():
                    app, title, ts = row
                    
                    # New session if gap > 5 minutes or different app
                    if not current_session or (last_ts and ts - last_ts > 300) or current_session["app"] != app:
                        if current_session and current_session["duration_minutes"] >= min_duration:
                            sessions.append(current_session)
                        
                        current_session = {
                            "app": app,
                            "start": datetime.fromtimestamp(ts),
                            "end": datetime.fromtimestamp(ts),
                            "duration_minutes": 0,
                            "entry_count": 1,
                            "titles": {title}
                        }
                    else:
                        current_session["end"] = datetime.fromtimestamp(ts)
                        current_session["duration_minutes"] = round(
                            (current_session["end"] - current_session["start"]).total_seconds() / 60, 1
                        )
                        current_session["entry_count"] += 1
                        current_session["titles"].add(title)
                    
                    last_ts = ts
                
                # Add last session
                if current_session and current_session["duration_minutes"] >= min_duration:
                    sessions.append(current_session)
                
                # Format sessions
                formatted_sessions = []
                for session in sorted(sessions, key=lambda x: x["duration_minutes"], reverse=True)[:20]:
                    formatted_sessions.append({
                        "app": session["app"],
                        "date": session["start"].strftime("%Y-%m-%d"),
                        "start_time": session["start"].strftime("%H:%M"),
                        "end_time": session["end"].strftime("%H:%M"),
                        "duration_minutes": session["duration_minutes"],
                        "entry_count": session["entry_count"],
                        "unique_activities": len(session["titles"])
                    })
                
                return {
                    "min_duration": min_duration,
                    "days_analyzed": days_back,
                    "total_sessions": len(sessions),
                    "sessions": formatted_sessions
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def get_productivity_insights(self, args: dict) -> dict:
        """Get productivity insights for a specific date"""
        try:
            date_str = args.get("date", "latest")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Determine date
                if date_str == "latest":
                    cursor.execute("SELECT MAX(timestamp) FROM entries")
                    max_ts = cursor.fetchone()[0]
                    if not max_ts:
                        return {"error": "No data"}
                    target_date = datetime.fromtimestamp(max_ts).date()
                else:
                    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                start_ts = int(datetime.combine(target_date, datetime.min.time()).timestamp())
                end_ts = int(datetime.combine(target_date, datetime.max.time()).timestamp())
                
                # Get hourly distribution
                cursor.execute("""
                    SELECT strftime('%H', datetime(timestamp, 'unixepoch')) as hour,
                           COUNT(*) as count
                    FROM entries
                    WHERE timestamp BETWEEN ? AND ?
                    GROUP BY hour
                    ORDER BY hour
                """, (start_ts, end_ts))
                
                hourly_data = {}
                for hour, count in cursor.fetchall():
                    hourly_data[f"{hour}:00"] = count
                
                # Get app summary
                cursor.execute("""
                    SELECT app, COUNT(*) as count
                    FROM entries
                    WHERE timestamp BETWEEN ? AND ?
                    GROUP BY app
                    ORDER BY count DESC
                    LIMIT 10
                """, (start_ts, end_ts))
                
                top_apps = []
                total_entries = 0
                for app, count in cursor.fetchall():
                    top_apps.append({"app": app, "entries": count})
                    total_entries += count
                
                # Find peak hours
                peak_hours = sorted(hourly_data.items(), key=lambda x: x[1], reverse=True)[:3]
                
                # Calculate active time span
                cursor.execute("""
                    SELECT MIN(timestamp), MAX(timestamp)
                    FROM entries
                    WHERE timestamp BETWEEN ? AND ?
                """, (start_ts, end_ts))
                
                min_ts, max_ts = cursor.fetchone()
                active_hours = round((max_ts - min_ts) / 3600, 1) if min_ts and max_ts else 0
                
                return {
                    "date": str(target_date),
                    "total_entries": total_entries,
                    "active_hours": active_hours,
                    "top_apps": top_apps,
                    "peak_hours": [{"hour": h, "entries": c} for h, c in peak_hours],
                    "hourly_distribution": hourly_data,
                    "avg_entries_per_hour": round(total_entries / max(active_hours, 1), 1)
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def search_activities(self, args: dict) -> dict:
        """Search activities by keyword"""
        try:
            keyword = args.get("keyword", "")
            limit = args.get("limit", 20)
            
            if not keyword:
                return {"error": "Keyword required"}
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT app, title, COUNT(*) as count,
                           MIN(timestamp) as first_seen,
                           MAX(timestamp) as last_seen
                    FROM entries
                    WHERE title LIKE ?
                    GROUP BY app, title
                    ORDER BY count DESC
                    LIMIT ?
                """, (f"%{keyword}%", limit))
                
                results = []
                for row in cursor.fetchall():
                    app, title, count, first_ts, last_ts = row
                    results.append({
                        "app": app,
                        "title": title,
                        "count": count,
                        "first_seen": datetime.fromtimestamp(first_ts).isoformat(),
                        "last_seen": datetime.fromtimestamp(last_ts).isoformat()
                    })
                
                return {
                    "keyword": keyword,
                    "total_results": len(results),
                    "results": results
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def get_database_info(self) -> dict:
        """Get database information"""
        try:
            if not Path(self.db_path).exists():
                return {"error": "Database not found"}
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM entries")
                total_entries = cursor.fetchone()[0]
                
                cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM entries")
                min_ts, max_ts = cursor.fetchone()
                
                cursor.execute("SELECT COUNT(DISTINCT app) FROM entries")
                unique_apps = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT title) FROM entries")
                unique_titles = cursor.fetchone()[0]
                
                days_of_data = 0
                if min_ts and max_ts:
                    days_of_data = round((max_ts - min_ts) / 86400, 1)
                
                return {
                    "database_path": self.db_path,
                    "total_entries": total_entries,
                    "unique_apps": unique_apps,
                    "unique_titles": unique_titles,
                    "days_of_data": days_of_data,
                    "date_range": {
                        "start": datetime.fromtimestamp(min_ts).isoformat() if min_ts else None,
                        "end": datetime.fromtimestamp(max_ts).isoformat() if max_ts else None
                    },
                    "size_mb": round(Path(self.db_path).stat().st_size / 1024 / 1024, 2)
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
                    server_name="openrecall-mcp",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="OpenRecall MCP Server")
    parser.add_argument("--db-path", required=True, help="Path to OpenRecall database")
    
    args = parser.parse_args()
    
    if not Path(args.db_path).exists():
        print(f"ERROR: Database not found: {args.db_path}", file=sys.stderr)
        sys.exit(1)
    
    server = OpenRecallMCP(args.db_path)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()