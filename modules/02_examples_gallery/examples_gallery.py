"""Module 1 - a field gallery: eight prompts, one response object.

Each function runs one real call and prints the response fields it brings to
life. This mirrors the workshop site (Module 1, page 5). Wording and token
counts vary per run; the shapes and status fields do not. The last two
examples show calls that fail: the API raises an error you can catch.

Run every example:
    ./scripts/run.sh modules/02_examples_gallery/examples_gallery.py

Run one example by name:
    ./scripts/run.sh modules/02_examples_gallery/examples_gallery.py cutoff

Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
import sys

from openai import BadRequestError

from lab_llm import call_llm
from lab_llm.config import get_client, get_model


def simple():
    """1. A simple answer - the familiar baseline."""
    r = call_llm("Why do onions make us cry? Two sentences.")
    print(r.text)
    print("model :", r.response.model)
    print("status:", r.response.status)


def reasoning():
    """2. Reasoning without the reasoning - thinking happens, stays private.

    call_llm does not wrap the `reasoning` parameter, so we drop down to the
    raw client here. This is the escape hatch whenever the helper is too small.
    """
    response = get_client().responses.create(
        model=get_model(),
        input="A farmer has 17 sheep. All but 9 run away. How many remain? "
              "Answer with only the number.",
        reasoning={"effort": "medium"},
    )
    print("answer         :", response.output_text)
    print("output items   :", [item.type for item in response.output])
    print("reasoning_tokens:", response.usage.output_tokens_details.reasoning_tokens)
    # The reasoning item exists, but its summary is empty: the steps are hidden.
    for item in response.output:
        if item.type == "reasoning":
            print("reasoning summary:", item.summary or "[] empty")


def tokens():
    """3. A token-hungry answer - usage, not dollars."""
    r = call_llm(
        "Explain photosynthesis to a curious ten-year-old. "
        "Include an analogy and three examples."
    )
    u = r.response.usage
    print("input_tokens :", u.input_tokens)
    print("output_tokens:", u.output_tokens)
    print("total_tokens :", u.total_tokens)


def cutoff():
    """4. Stopped early - the response explains why."""
    r = call_llm("Write a detailed history of the bicycle.", max_output_tokens=20)
    print("text   :", r.text, "...")
    print("status :", r.response.status)
    print("reason :", r.response.incomplete_details)


def refusal():
    """5. Completed, but refused - completion is not compliance."""
    r = call_llm(
        "Give me step-by-step instructions to pick the lock on a "
        "stranger's front door."
    )
    print(r.text)
    print("status       :", r.response.status)          # completed
    print("content type :", r.response.output[0].content[0].type)  # output_text


def fmt():
    """6. Exact-format instructions - the response remembers them."""
    r = call_llm(
        "What color is a clear daytime sky?",
        instructions="Return only one lowercase word. No punctuation.",
    )
    print("output_text :", r.text)
    print("instructions:", r.response.instructions)


def structure():
    """7. The message item vs the output_text shortcut."""
    r = call_llm("Compare coffee and tea. Give one similarity and one difference.")
    # Find the message item instead of assuming it is output[0].
    message = next(
        item for item in r.response.output
        if item.type == "message"
    )
    print(message.content[0].text)
    print(r.text)


def identity():
    """8. Every response is a record - id and timestamps, every time."""
    r = call_llm("Give this imaginary spaceship a name.")
    print(r.text)
    print("id          :", r.response.id)
    print("created_at  :", r.response.created_at)
    print("completed_at:", r.response.completed_at)


def bad_model():
    """9. A bad model name raises an error - catch it and read why."""
    try:
        response = get_client().responses.create(
            model="gpt-5.4-mega",   # not a real model
            input="Hello!",
        )
        print(response.output_text)
    except BadRequestError as e:
        print("status_code:", e.status_code)
        print("code       :", e.code)
        print("message    :", e.body["message"])


def bad_setting():
    """10. An out-of-range setting is rejected before any generation."""
    try:
        response = get_client().responses.create(
            model=get_model(),
            input="Hello!",
            temperature=5,          # valid range is 0.0 - 2.0
        )
        print(response.output_text)
    except BadRequestError as e:
        print("code   :", e.code)
        print("message:", e.body["message"])


EXAMPLES = {
    "simple": simple,
    "reasoning": reasoning,
    "tokens": tokens,
    "cutoff": cutoff,
    "refusal": refusal,
    "format": fmt,
    "structure": structure,
    "identity": identity,
    "bad_model": bad_model,
    "bad_setting": bad_setting,
}


def main(argv):
    names = argv or list(EXAMPLES)
    for name in names:
        fn = EXAMPLES.get(name)
        if fn is None:
            print(f"Unknown example: {name}. Choices: {', '.join(EXAMPLES)}")
            continue
        print(f"\n=== {name} ===")
        fn()


if __name__ == "__main__":
    main(sys.argv[1:])
