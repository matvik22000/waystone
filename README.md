# Waystone - Reticulum Network Search Engine

**Waystone** is a distributed search engine designed to operate within the Reticulum mesh network. It crawls and indexes content from Nomad Network nodes, providing search capabilities across the decentralized network.

### NomadAPI

NomadAPI is a flask-like interface to RNS. Eventually it will be separated into a standalone python library. You can see usage examples in "examples" folder.

## Architecture Overview

### Core Components

**Search Engine** (`src/core/data/search.py:72`)
- Built on Whoosh full-text search library
- Supports document indexing with citation-based ranking
- Features text highlighting and duplicate filtering
- Indexes: URL, text content, node names, addresses, owners

**Web Crawler** (`src/core/crawl.py:121`) 
- Multi-threaded crawler for Nomad Network nodes
- Extracts and follows internal/external links
- Processes Micron markup (`.mu` files)
- Updates search index and citation graphs

**Reticulum Integration** (`src/core/rns.py:14`)
- Creates RNS destinations and identity management
- Handles network announces from peers and nodes
- Manages connections to the mesh network

**API Framework** (`src/api/app.py:32`)
- Custom web framework (NomadAPI) for Reticulum
- Template rendering with Jinja2
- Request handling and routing
- User session management

### Key Features

**Distributed Search**: Indexes content across multiple Reticulum nodes with citation-based relevance scoring

**Network Discovery**: Automatically discovers peers and nodes through RNS announces

**Citation Tracking**: Maintains a graph of inter-node references to improve search ranking

**Template System**: Uses Micron markup (`.mu` files) for UI rendering compatible with Nomad Network clients

**Scheduled Operations**: Periodic crawling and network announces via scheduler

### Dependencies

- **RNS**: Reticulum network protocol
- **LXMF**: Nomad Network messaging
- **Whoosh**: Full-text search indexing
- **Jinja2**: Template engine
- **PySerial**: Hardware interface support

### File Structure

```
src/
├── api/          # Web framework and request handling
├── config/       # Configuration management  
├── core/         # Search engine and crawling logic
│   ├── crawler/  # Web crawling components
│   └── data/     # Search index and data storage
storage/          # Persistent data (indexes, announces, etc.)
templates/        # Micron markup UI templates
```

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables in `.env` file

3. Start the search engine:
```bash
./start.sh
```

### Entry Points

- **Main**: `src/main.py:4` → `src/core/main.py:8`
- **Startup**: `start.sh:1` loads environment and launches application
- **Web Interface**: Available on configured Reticulum destination

## How It Works

The system operates as a decentralized search service, automatically discovering and indexing content across the Reticulum mesh network while providing a familiar search interface to users.

1. **Network Discovery**: Waystone listens for RNS announces to discover active nodes and peers
2. **Crawling**: Periodically crawls discovered nodes to index their content
3. **Indexing**: Processes Micron markup files and builds searchable index
4. **Search**: Provides search interface with citation-weighted results
5. **UI**: Serves search interface through Micron templates compatible with Nomad Network

### Configuration

The application uses environment-based configuration through the `Config` class in `src/config/config.py`. Key settings include:

- RNS configuration directory
- Node identity path
- Storage paths
- Crawler thread count
- Announce intervals

### Storage

Persistent data is stored in the `storage/` directory:
- `search_index/`: Whoosh search index files
- `announces.json`: Network announce data
- `citations.json`: Inter-node citation graph
- `queries.json`: Search query history
- `api_user_data.json`: User session data