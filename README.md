# File Organizer Agent

A simple AI agent that analyzes files in a directory and organizes them by type. Built with the Anthropic Claude SDK.

## Features

- Scans directories and lists files with their types and sizes
- Suggests logical organization structure (documents, images, code, etc.)
- Asks for confirmation before moving files
- `--dry-run` mode to preview changes without moving anything

## Installation

```bash
pip install -r requirements.txt
```

Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

## Usage

Organize a directory (with confirmation prompts):
```bash
python agent.py /path/to/directory
```

Preview what would happen without moving files:
```bash
python agent.py /path/to/directory --dry-run
```

## How It Works

This agent demonstrates the core agentic loop pattern:

1. **Tool Definitions** - JSON schema defining what actions Claude can take
2. **Tool Handlers** - Python functions that execute when Claude requests a tool
3. **Agentic Loop** - Keeps calling Claude until `stop_reason == "end_turn"`

```
User Request → Claude → Tool Request → Execute Tool → Result → Claude → ...
```

Claude doesn't execute tools directly - it requests them. We execute and send results back.

## Tools

| Tool | Description |
|------|-------------|
| `list_directory` | List files and folders with types and sizes |
| `create_folder` | Create a new folder |
| `move_file` | Move a file to a new location |
