"""Module 1 - the same two-file call, using lab_llm.

Run:  ./scripts/run.sh examples/05_files/nicer_example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from lab_llm import Conversation, temporary_file  # reusable helpers

with (
    temporary_file("data/transcripts.csv") as transcripts,  # the data
    temporary_file("data/instructions.txt") as rubric,      # the rubric
    Conversation() as chat,                                 # one conversation
):
    result = chat.send(                     # both files and the prompt in one turn
        "Use the instructions file to rate each transcript in the CSV for anxiety "
        "on a 0-100 scale. Give the id and the score.",
        file_ids=[transcripts.id, rubric.id],  # reference both uploaded files
    )

    print(result.text)                      # the model output

# Conversation and uploaded files deleted. Also runs after an error.
