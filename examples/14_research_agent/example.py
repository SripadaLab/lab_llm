"""A bounded research agent: inspect, estimate, approve, run, check, report."""
from agents import Agent, Runner

from lab_llm.config import get_model
from pilot_tools import TOOLS


director = Agent(
    name="Research Pilot Director",
    instructions=(
        "Help the researcher evaluate the fixed demo study. First inspect it. "
        "Then estimate a three-transcript pilot. Explain any input issues. "
        "If the usable inputs support a pilot, run it. After it runs, check "
        "the results and save the HTML review. Never invent tool results."
    ),
    tools=TOOLS,
    model=get_model(),
)


def main() -> None:
    """Run the agent and resolve each approval in the terminal."""
    result = Runner.run_sync(
        director,
        "Can we run an anxiety-rating pilot on this study folder?",
    )

    # Approval is an enforced pause, not a polite sentence in the prompt.
    while result.interruptions:
        print(f"\nApproval required for {len(result.interruptions)} tool call(s).")
        if input("Approve? [y/N] ").strip().lower() != "y":
            raise SystemExit("Stopped. No approval given.")
        state = result.to_state()
        for interruption in result.interruptions:
            state.approve(interruption)
        result = Runner.run_sync(director, state)

    print("\n" + str(result.final_output))


if __name__ == "__main__":
    main()
