import anthropic
import argparse
import os
import json
import shutil

client = anthropic.Anthropic()

DRY_RUN = False

tools = [
    {
        "name": "list_directory",
        "description": "List all files and folders in a directory with their types and sizes",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "move_file",
        "description": "Move a file from one location to another",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The current file path"
                },
                "destination": {
                    "type": "string",
                    "description": "The new file path"
                }
            },
            "required": ["source", "destination"]
        }
    },
    {
        "name": "create_folder",
        "description": "Create a new folder",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The folder path to create"
                }
            },
            "required": ["path"]
        }
    }
]


def list_directory(path: str) -> str:
    try:
        entries = []
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            if os.path.isfile(full_path):
                size = os.path.getsize(full_path)
                ext = os.path.splitext(entry)[1] or "(no extension)"
                entries.append(f"FILE: {entry} | Extension: {ext} | Size: {size} bytes")
            else:
                entries.append(f"DIR:  {entry}/")
        return "\n".join(entries) if entries else "Directory is empty"
    except Exception as e:
        return f"Error: {e}"


def move_file(source: str, destination: str) -> str:
    if DRY_RUN:
        return f"[DRY-RUN] Would move {source} to {destination}"
    try:
        dest_dir = os.path.dirname(destination)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        shutil.move(source, destination)
        return f"Moved {source} to {destination}"
    except Exception as e:
        return f"Error: {e}"


def create_folder(path: str) -> str:
    if DRY_RUN:
        return f"[DRY-RUN] Would create folder: {path}"
    try:
        os.makedirs(path, exist_ok=True)
        return f"Created folder: {path}"
    except Exception as e:
        return f"Error: {e}"


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "list_directory":
        return list_directory(tool_input["path"])
    elif tool_name == "move_file":
        return move_file(tool_input["source"], tool_input["destination"])
    elif tool_name == "create_folder":
        return create_folder(tool_input["path"])
    else:
        return f"Unknown tool: {tool_name}"


def run_agent(user_request: str, dry_run: bool = False):
    global DRY_RUN
    DRY_RUN = dry_run

    mode_str = " [DRY-RUN MODE]" if dry_run else ""
    print(f"\n{'='*60}")
    print(f"User Request: {user_request}{mode_str}")
    print(f"{'='*60}\n")

    messages = [{"role": "user", "content": user_request}]

    if dry_run:
        system_prompt = """You are a helpful file organizer agent in PREVIEW MODE.
This is a dry-run - no files will actually be moved or folders created.
Your job is to:
1. Look at files in directories the user specifies
2. Show exactly what organization you would perform
3. Go ahead and call the tools - they will simulate the actions

Since this is a preview, proceed with the full organization plan to show the user what would happen."""
    else:
        system_prompt = """You are a helpful file organizer agent. Your job is to:
1. Look at files in directories the user specifies
2. Suggest a logical organization structure
3. Ask for confirmation before moving any files
4. Organize files by type (documents, images, code, etc.)

Always explain your reasoning. Be conservative - ask before moving files."""

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        for block in response.content:
            if hasattr(block, "text"):
                print(f"Agent: {block.text}\n")

        if response.stop_reason == "end_turn":
            print("[Agent finished]")
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"[Tool Call] {block.name}")
                    print(f"[Input] {json.dumps(block.input, indent=2)}")

                    result = process_tool_call(block.name, block.input)
                    print(f"[Result] {result}\n")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="File Organizer Agent")
    parser.add_argument("directory", help="Directory to organize")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without actually moving files"
    )
    args = parser.parse_args()

    run_agent(
        f"Please look at the files in {args.directory} and suggest how to organize them.",
        dry_run=args.dry_run
    )

