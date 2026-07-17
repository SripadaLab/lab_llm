"""Let the model inspect a study by calling one bounded Python function."""
import json
from pathlib import Path

from openai import OpenAI

from lab_llm import ItemBank
from lab_llm.config import get_model


STUDY_PATH = Path("examples/13_tool_calling/study")


def inspect_study() -> str:
    """Inspect the fixed demo study. No model call happens inside this tool."""
    transcript_files = sorted((STUDY_PATH / "transcripts").glob("*.txt"))
    blank_files = [
        path.name
        for path in transcript_files
        if not path.read_text(encoding="utf-8").strip()
    ]
    usable_files = [
        path.name for path in transcript_files if path.name not in blank_files
    ]
    items = ItemBank.from_csv(STUDY_PATH / "items.csv")
    issues = (
        [f"Blank transcripts: {', '.join(blank_files)}"]
        if blank_files else []
    )
    report = {
        "transcripts_found": len(transcript_files),
        "usable_transcripts": len(usable_files),
        "items": len(items),
        "possible_jobs": len(usable_files) * len(items),
        "ready": not issues,
        "issues": issues,
    }
    return json.dumps(report)


# The schema tells the model what it may request. This tool takes no arguments.
INSPECT_TOOL = {
    "type": "function",
    "name": "inspect_study",
    "description": "Inspect the demo study and report files, items, and issues.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}


model = get_model()
client = OpenAI()
input_items = [{
    "role": "user",
    "content": "Is the demo study ready for a rating pilot? Be concise.",
}]

# One user request can require several model-tool-model rounds.
for round_number in range(1, 9):
    if round_number == 1:
        print("\n[1/5] Sending the task prompt and tool definition.")
    else:
        print("\n[5/5] Continuing with the tool result.")

    response = client.responses.create(
        model=model,
        input=input_items,
        tools=[INSPECT_TOOL],
    )
    print(f"[2/5] Response received: {response.id}")
    print("      Checking for function calls.")

    # Preserve every output item, including reasoning and function calls.
    input_items += response.output
    calls = [item for item in response.output if item.type == "function_call"]
    if not calls:
        print("[5/5] No function call requested. Final answer:\n")
        print(response.output_text)
        break

    for call in calls:
        print(f"[3/5] Function requested: {call.name}")
        print(f"      Arguments: {call.arguments}")
        print("      Checking the function name.")
        if call.name != "inspect_study":
            raise ValueError(f"Unknown tool: {call.name}")
        print("      Running inspect_study().")
        result = inspect_study()
        print(f"      Function output: {result}")
        input_items.append({
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": result,
        })
        print(f"[4/5] Output saved for call_id: {call.call_id}")
else:
    raise RuntimeError("Tool loop exceeded eight rounds")
