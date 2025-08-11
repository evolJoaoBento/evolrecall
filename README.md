```
   ____                   ____                  ____   
  / __ \____  ___  ____  / __ \___  _________ _/ / /   
 / / / / __ \/ _ \/ __ \/ /_/ / _ \/ ___/ __ `/ / /    
/ /_/ / /_/ /  __/ / / / _, _/  __/ /__/ /_/ / / /     
\____/ .___/\___/_/ /_/_/ |_|\___/\___/\__,_/_/_/      
    /_/                                                                                                                         
```
**Enjoy this project?** Show your support by starring it! ⭐️ Thank you!

Join our [Discord](https://discord.gg/RzvCYRgUkx) and/or [Telegram](https://t.me/+5DULWTesqUYwYjY0) community to stay informed of updates!

# Take Control of Your Digital Memory

OpenRecall is a fully open-source, privacy-first alternative to proprietary solutions like Microsoft's Windows Recall or Limitless' Rewind.ai. With OpenRecall, you can easily access your digital history, enhancing your memory and productivity without compromising your privacy.

## What does it do?

OpenRecall captures your digital history through regularly taken snapshots, which are essentially screenshots. The text and images within these screenshots are analyzed and made searchable, allowing you to quickly find specific information by typing relevant keywords into OpenRecall. You can also manually scroll back through your history to revisit past activities.

https://github.com/openrecall/openrecall/assets/16676419/cfc579cb-165b-43e4-9325-9160da6487d2

## Why Choose OpenRecall?

OpenRecall offers several key advantages over closed-source alternatives:

- **Transparency**: OpenRecall is 100% open-source, allowing you to audit the source code for potential backdoors or privacy-invading features.
- **Cross-platform Support**: OpenRecall works on Windows, macOS, and Linux, giving you the freedom to use it on your preferred operating system.
- **Privacy-focused**: Your data is stored locally on your device, no internet connection or cloud is required. In addition, you have the option to encrypt the data on a removable disk for added security, read how in our [guide](docs/encryption.md) here. 
- **Hardware Compatibility**: OpenRecall is designed to work with a [wide range of hardware](docs/hardware.md), unlike proprietary solutions that may require specific certified devices.

<p align="center">
  <a href="https://twitter.com/elonmusk/status/1792690964672450971" target="_blank">
    <img src="images/black_mirror.png" alt="Elon Musk Tweet" width="400">
  </a>
</p>

## Features

- **Time Travel**: Revisit and explore your past digital activities seamlessly across Windows, macOS, or Linux.
- **Local-First AI**: OpenRecall harnesses the power of local AI processing to keep your data private and secure.
- **Semantic Search**: Advanced local OCR interprets your history, providing robust semantic search capabilities.
- **Full Control Over Storage**: Your data is stored locally, giving you complete control over its management and security.

<p align="center">
  <img src="images/lisa_rewind.webp" alt="Lisa Rewind" width="400">
</p>


## Comparison



| Feature          | OpenRecall                    | Windows Recall                                  | Rewind.ai                              |
|------------------|-------------------------------|--------------------------------------------------|----------------------------------------|
| Transparency     | Open-source                   | Closed-source                                    | Closed-source                          |
| Supported Hardware | All                         | Copilot+ certified Windows hardware              | M1/M2 Apple Silicon                    |
| OS Support       | Windows, macOS, Linux         | Windows                                          | macOS                                  |
| Privacy          | On-device, self-hosted        | Microsoft's privacy policy applies               | Connected to ChatGPT                   |
| Cost             | Free                          | Part of Windows 11 (requires specialized hardware) | Monthly subscription                   |

## Quick links
- [Roadmap](https://github.com/orgs/openrecall/projects/2) and you can [vote for your favorite features](https://github.com/openrecall/openrecall/discussions/9#discussion-6775473)
- [FAQ](https://github.com/openrecall/openrecall/wiki/FAQ)

## Get Started

### Prerequisites
- Python 3.11
- MacOSX/Windows/Linux
- Git

To install:
```
python3 -m pip install --upgrade --no-cache-dir git+https://github.com/openrecall/openrecall.git
```

To run:
```
python3 -m openrecall.app
```
Open your browser to:
[http://localhost:8082](http://localhost:8082) to access OpenRecall.

## Arguments
`--storage-path` (default: user data path for your OS): allows you to specify the path where the screenshots and database should be stored. We recommend [creating an encrypted volume](docs/encryption.md) to store your data.

`--primary-monitor-only` (default: False): only record the primary monitor (rather than individual screenshots for other monitors)

## Uninstall instructions

To uninstall OpenRecall and remove all stored data:

1. Uninstall the package:
   ```
   python3 -m pip uninstall openrecall
   ```

2. Remove stored data:
   - On Windows:
     ```
     rmdir /s %APPDATA%\openrecall
     ```
   - On macOS:
     ```
     rm -rf ~/Library/Application\ Support/openrecall
     ```
   - On Linux:
     ```
     rm -rf ~/.local/share/openrecall
     ```

Note: If you specified a custom storage path at any time using the `--storage-path` argument, make sure to remove that directory too.

## Contribute

As an open-source project, we welcome contributions from the community. If you'd like to help improve OpenRecall, please submit a pull request or open an issue on our GitHub repository.

## Contact the maintainers
mail@datatalk.be

## License

OpenRecall is released under the [AGPLv3](https://opensource.org/licenses/AGPL-3.0), ensuring that it remains open and accessible to everyone.

## 📋 Table of Contents

- [Installation](#installation)
- [MCP Servers](#mcp-servers)
  - [OpenRecall MCP Server](#openrecall-mcp-server)
  - [Documentation MCP Server](#documentation-mcp-server)
  - [Claude Desktop Configuration](#claude-desktop-configuration)
- [Database Viewer](#database-viewer)
  - [Features](#database-viewer-features)
  - [Configuration](#database-viewer-configuration)
  - [Usage](#database-viewer-usage)
- [Configuration Files](#configuration-files)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

## 🛠️ Installation

```bash
# Install OpenRecall
pip install openrecall

# Or install from source
git clone <repository-url>
cd openrecall
pip install -e .
```

## 🔌 MCP Servers

OpenRecall provides two MCP servers that integrate with Claude Desktop, allowing you to query and analyze your data directly through AI conversations.

### OpenRecall MCP Server

The OpenRecall MCP Server provides access to your activity tracking data.

#### Available Tools:
- `query_activities` - Search and filter activities by time range and application
- `get_app_statistics` - Get usage statistics for applications
- `find_focus_sessions` - Identify continuous work sessions
- `get_productivity_insights` - Analyze productivity patterns
- `search_activities` - Search activities by keyword
- `get_database_info` - Get database statistics and information

#### Usage Examples:
```
# Ask Claude:
"Show me my most used applications this week"
"Find my longest focus sessions from yesterday" 
"What was I working on between 2-4 PM today?"
"Give me productivity insights for this month"
```

### Documentation MCP Server

The Documentation MCP Server manages a property-based documentation system with hierarchical data organization.

#### Available Tools:
- `create_property` - Create new documentation properties
- `get_property` - Retrieve property by key or ID
- `search_properties` - Search properties with full-text search
- `list_properties` - List properties with filtering options
- `update_property` - Update existing properties
- `delete_property` - Remove properties
- `create_tag` - Create organizational tags
- `get_tag_tree` - Get hierarchical tag structure
- `rebuild_search_index` - Refresh full-text search index

#### Usage Examples:
```
# Ask Claude:
"Create a property for my API documentation"
"Search for properties related to authentication"
"Show me the tag hierarchy for the project"
"Update the deployment property with new instructions"
```

### Claude Desktop Configuration

To use the MCP servers with Claude Desktop, you need to configure them in your Claude Desktop settings.

#### Configuration File Location:

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

#### Configuration Content:

Create or edit the `claude_desktop_config.json` file:

```json
{
  "mcpServers": {
    "openrecall-mcp": {
      "command": "python",
      "args": [
        "C:\\path\\to\\openrecall_mcp.py",
        "--db-path",
        "C:\\Users\\YourUsername\\AppData\\Roaming\\openrecall\\recall.db"
      ]
    },
    "documentation-mcp": {
      "command": "python",
      "args": [
        "C:\\path\\to\\documentation_mcp.py",
        "--db-path",
        "C:\\path\\to\\documentation.db"
      ]
    }
  }
}
```

#### Finding Your Database Paths:

**OpenRecall Database:**
```bash
python -c "import config; print('Database path:', config.appdata_folder + '\\recall.db')"
```

**Documentation Database:**
Usually located in the same directory as the MCP server files.

#### Setup Steps:

1. **Close Claude Desktop** completely
2. **Navigate to the config directory** using File Explorer
3. **Create or edit** `claude_desktop_config.json`
4. **Update the paths** to match your system
5. **Save the file**
6. **Restart Claude Desktop**

#### Verification:

After restart, you should see the MCP servers listed in Claude Desktop. Test by asking Claude to query your data:

```
"Show me my activity data from today"
"Create a documentation property for my project"
```

## 🌐 Database Viewer

The Database Viewer provides a modern web interface for browsing and managing your OpenRecall and documentation data.

### Database Viewer Features

#### 📊 **Activities Tab**
- View recent activities with time filtering
- Search activities by application or title
- Statistics cards showing total entries, unique apps, and data coverage
- Responsive data tables with pagination

#### 📋 **Properties Tab** 
- Browse documentation properties with type filtering
- Full-text search across property content
- Tag filtering and hierarchical organization
- Property tree view for nested data

#### 🏷️ **Tags Tab**
- Hierarchical tag management
- Project-based tag organization
- Visual tag tree with property counts
- Color-coded tag system

#### 📁 **Projects Tab**
- Project management and overview
- Property and tag counts per project
- Active/inactive project status
- Project creation and editing

#### 📈 **Statistics Tab**
- Database statistics and metrics
- Property type distribution
- Search index coverage
- Database size and performance metrics

#### ⚙️ **Settings Tab**
- Database path configuration
- Server settings (host, port)
- Interface preferences
- Configuration file management

### Database Viewer Configuration

The Database Viewer uses an INI configuration file for settings management.

#### Configuration File: `database_viewer.ini`

```ini
[database]
recall_db_path = C:\Users\YourUsername\AppData\Roaming\openrecall\recall.db
docs_db_path = documentation.db

[server]
host = 127.0.0.1
port = 8084

[interface]
auto_refresh_seconds = 30
default_page_size = 20

[metadata]
last_updated = 2024-01-01T00:00:00
version = 2.0.0
```

#### Configuration Options:

| Setting | Description | Default |
|---------|-------------|---------|
| `recall_db_path` | Path to OpenRecall activity database | (required) |
| `docs_db_path` | Path to documentation database | `documentation.db` |
| `host` | Web server bind address | `127.0.0.1` |
| `port` | Web server port | `8084` |
| `auto_refresh_seconds` | UI refresh interval | `30` |
| `default_page_size` | Items per page | `20` |

### Database Viewer Usage

#### Starting the Viewer:

```bash
# Basic usage (will create default config)
python database_viewer.py --recall-db path/to/recall.db

# With custom configuration file
python database_viewer.py --config my_config.ini

# Specify all options
python database_viewer.py --recall-db path/to/recall.db --docs-db path/to/docs.db --port 8085

# Create default configuration file
python database_viewer.py --create-config
```

#### Command Line Options:

| Option | Description |
|--------|-------------|
| `--config` | Path to configuration file |
| `--recall-db` | OpenRecall database path (overrides config) |
| `--docs-db` | Documentation database path (overrides config) |
| `--port` | Server port (overrides config) |
| `--host` | Server host (overrides config) |
| `--create-config` | Create default config file and exit |

#### Accessing the Interface:

1. Start the database viewer
2. Open your browser to `http://localhost:8084` (or configured port)
3. Use the navigation tabs to explore your data
4. Configure settings through the Settings tab

## 📁 Configuration Files

### Main Configuration: `database_viewer.ini`
- Database paths and connection settings
- Web server configuration
- UI preferences and defaults

### Claude Desktop: `claude_desktop_config.json`
- MCP server configuration
- Python command and argument specification
- Database path mapping for MCP servers

## 🔧 Troubleshooting

### Common Issues

#### MCP Server Connection Failed
```
ERROR: Database not found: C:\path\to\your\recall.db
```
**Solution:** Update the database path in `claude_desktop_config.json` with the actual path to your database.

#### Python Module Not Found
```
ModuleNotFoundError: No module named 'mcp'
```
**Solution:** Install the MCP SDK:
```bash
pip install mcp
```

#### Database Viewer Won't Start
```
ERROR: OpenRecall database not found
```
**Solution:** 
1. Check the database path in your configuration
2. Ensure OpenRecall has been running to create the database
3. Use `--create-config` to generate a default configuration

#### Port Already in Use
```
Address already in use
```
**Solution:** Either stop the existing service or use a different port:
```bash
python database_viewer.py --port 8085
```

### Debug Steps

1. **Verify Database Paths:**
   ```bash
   python -c "import os; print('Recall DB exists:', os.path.exists('path/to/recall.db'))"
   ```

2. **Test MCP Server Directly:**
   ```bash
   python openrecall_mcp.py --db-path path/to/recall.db
   ```

3. **Check Configuration:**
   ```bash
   python database_viewer.py --create-config
   cat database_viewer.ini
   ```

4. **Validate JSON Configuration:**
   Use an online JSON validator to check your `claude_desktop_config.json` syntax.

### Log Locations

- **Claude Desktop Logs:** Available in Claude Desktop's developer tools
- **Database Viewer:** Console output when running the server
- **MCP Servers:** stderr output visible in Claude Desktop logs

## 📚 API Reference

### OpenRecall MCP Server API

#### `query_activities(time_range, app_filter?, limit?)`
Query activities with time and application filters.

**Parameters:**
- `time_range`: "today" | "yesterday" | "week" | "month" | "all"
- `app_filter`: Optional application name filter
- `limit`: Maximum results (default: 20)

#### `get_app_statistics(time_range)`
Get application usage statistics.

**Parameters:**
- `time_range`: Time period for statistics

#### `find_focus_sessions(min_duration?, days_back?)`
Find continuous work sessions.

**Parameters:**
- `min_duration`: Minimum session length in minutes (default: 30)
- `days_back`: Days to analyze (default: 7)

### Documentation MCP Server API

#### `create_property(key, value, type?, parent_key?, tags?)`
Create a new documentation property.

**Parameters:**
- `key`: Unique identifier for the property
- `value`: Property content
- `type`: Property type (default: "text")
- `parent_key`: Parent property key for hierarchy
- `tags`: Array of tag names

#### `search_properties(query, limit?)`
Full-text search across properties.

**Parameters:**
- `query`: Search query string
- `limit`: Maximum results (default: 10)

### Database Viewer Web API

The Database Viewer exposes REST endpoints for web interface functionality:

- `GET /api/activities` - Get activity data
- `GET /api/properties` - Get documentation properties
- `GET /api/tags` - Get tag hierarchy
- `GET /api/projects` - Get project list
- `GET /api/database-stats` - Get database statistics
- `GET /api/config` - Get current configuration
- `POST /api/config` - Update configuration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

[Add your license information here]

## 🆘 Support

For support and questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review Claude Desktop MCP documentation
- Open an issue on the repository

---

**Happy tracking and documenting! 🚀**

