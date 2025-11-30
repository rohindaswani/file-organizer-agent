import anthropic
import argparse
import os
import json
import shutil

client = anthropic.Anthropic()

# Global flag for dry-run mode
DRY_RUN = False

# =============================================================================
# STEP 2: DEFINE THE TOOLS
# =============================================================================
# Tools are defined as a list of dictionaries. Each tool has:
#   - name: What Claude will call it
#   - description: Helps Claude understand WHEN to use it
#   - input_schema: JSON Schema defining the parameters
#
# Think of this as the "API contract" you're giving Claude.
# =============================================================================

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

# =============================================================================
# STEP 3: IMPLEMENT TOOL HANDLERS
# =============================================================================
# These are regular Python functions. Claude doesn't run them directly -
# Claude just tells us which tool to call and with what arguments.
# We run the function and send the result back to Claude.
# =============================================================================


def list_directory(path: str) -> str:
    """List contents of a directory with file info."""
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
    """Move a file to a new location."""
    if DRY_RUN:
        return f"[DRY-RUN] Would move {source} to {destination}"
    try:
        # Create destination directory if it doesn't exist
        dest_dir = os.path.dirname(destination)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        shutil.move(source, destination)
        return f"Moved {source} to {destination}"
    except Exception as e:
        return f"Error: {e}"


def create_folder(path: str) -> str:
    """Create a new folder."""
    if DRY_RUN:
        return f"[DRY-RUN] Would create folder: {path}"
    try:
        os.makedirs(path, exist_ok=True)
        return f"Created folder: {path}"
    except Exception as e:
        return f"Error: {e}"


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    """
    Route a tool call to the right function.
    This is the bridge between Claude's requests and our actual code.
    """
    if tool_name == "list_directory":
        return list_directory(tool_input["path"])
    elif tool_name == "move_file":
        return move_file(tool_input["source"], tool_input["destination"])
    elif tool_name == "create_folder":
        return create_folder(tool_input["path"])
    else:
        return f"Unknown tool: {tool_name}"


# =============================================================================
# STEP 4: THE AGENTIC LOOP
# =============================================================================
# This is the heart of an agent. The loop:
#   1. Send message to Claude with tools available
#   2. Check stop_reason:
#      - "end_turn" → Claude is done, exit loop
#      - "tool_use" → Claude wants to use a tool
#   3. If tool_use: execute tool, send result back, continue loop
#
# The key insight: Claude doesn't execute tools. It REQUESTS them.
# We execute, then tell Claude what happened.
# =============================================================================


def run_agent(user_request: str, dry_run: bool = False):
    """Run the file organizer agent."""
    global DRY_RUN
    DRY_RUN = dry_run

    mode_str = " [DRY-RUN MODE]" if dry_run else ""
    print(f"\n{'='*60}")
    print(f"User Request: {user_request}{mode_str}")
    print(f"{'='*60}\n")

    # Conversation history - this grows as we go
    messages = [{"role": "user", "content": user_request}]

    # System prompt guides the agent's behavior
    # In dry-run mode, tell the agent to go ahead and show the full plan
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

    # THE AGENTIC LOOP
    while True:
        # 1. Call Claude with our messages and tools
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        # 2. Print any text Claude returns
        for block in response.content:
            if hasattr(block, "text"):
                print(f"Agent: {block.text}\n")

        # 3. Check WHY Claude stopped
        #    - "end_turn" means Claude is done talking
        #    - "tool_use" means Claude wants to use a tool
        if response.stop_reason == "end_turn":
            print("[Agent finished]")
            break

        # 4. If Claude wants to use tools, process them
        if response.stop_reason == "tool_use":
            # Add Claude's response to conversation history
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool Claude requested
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"[Tool Call] {block.name}")
                    print(f"[Input] {json.dumps(block.input, indent=2)}")

                    # Run the tool and get result
                    result = process_tool_call(block.name, block.input)
                    print(f"[Result] {result}\n")

                    # Format result for Claude
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,  # Must match the tool_use id!
                        "content": result
                    })

            # Send tool results back to Claude
            messages.append({"role": "user", "content": tool_results})

            # Loop continues - Claude will see the results and decide what's next


# =============================================================================
# MAIN - Run the agent
# =============================================================================
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

