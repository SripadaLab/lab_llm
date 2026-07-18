"""Chat with an agent that investigates a small synthetic study."""
from agents import (
    Agent,
    CodeInterpreterTool,
    RunHooks,
    Runner,
    SQLiteSession,
)

from lab_llm.config import get_model
from study_tools import TOOLS


class TerminalHooks(RunHooks):
    """Show actions without exposing private model reasoning."""

    async def on_llm_start(
        self, context, agent, system_prompt, input_items
    ) -> None:
        print("  -> model request")

    async def on_tool_start(self, context, agent, tool) -> None:
        print(f"  -> {tool.name}")

    async def on_llm_end(self, context, agent, response) -> None:
        # Hosted tools run inside the model response, not in local Python.
        if any(
            getattr(item, "type", "") == "code_interpreter_call"
            for item in response.output
        ):
            print("  -> code_interpreter")


investigator = Agent(
    name="Study Investigator",
    instructions=(
        "Answer scientific questions about the fixed synthetic study. "
        "Investigate before making claims: list files, read relevant evidence, "
        "and compare sources. Use Code Interpreter for calculations, tables, "
        "counts, or cross-file checks. The Python sandbox cannot see local "
        "files directly, so pass it data found with the study tools. Cite the "
        "study filenames that support important claims. Distinguish evidence "
        "from inference. Say when the available files cannot answer a question."
    ),
    tools=[
        *TOOLS,
        CodeInterpreterTool({
            "type": "code_interpreter",
            "container": {"type": "auto"},
        }),
    ],
    model=get_model(),
)


def main() -> None:
    """Run a multi-turn terminal chat with local conversation memory."""
    session = SQLiteSession("study-investigator")
    hooks = TerminalHooks()

    print("Study Investigator")
    print("Ask a scientific question about the demo study. Type 'quit' to exit.")
    print("Try: Is this study ready for analysis?\n")

    while True:
        try:
            question = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if question.lower() in {"quit", "exit"}:
            print("Goodbye.")
            break
        if not question:
            continue

        try:
            result = Runner.run_sync(
                investigator,
                question,
                session=session,
                hooks=hooks,
                max_turns=12,
            )
        except Exception as exc:
            print(f"\nCould not complete that turn: {exc}\n")
            continue

        print(f"\nAgent > {result.final_output}\n")


if __name__ == "__main__":
    main()
