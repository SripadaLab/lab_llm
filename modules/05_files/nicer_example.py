"""Module 1 - the same two-file call, using lab_llm.

Run:  ./scripts/run.sh modules/05_files/nicer_example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from lab_llm import Conversation, delete_file, upload_file  # reusable helpers

transcripts = upload_file("data/transcripts.csv")  # the data
rubric = upload_file("data/instructions.txt")      # the rating rubric

chat = Conversation()                       # one server-side conversation
result = chat.send(                         # both files and the prompt in one turn
    "Use the instructions file to rate each transcript in the CSV for anxiety "
    "on a 0-100 scale. Give the id and the score.",
    file_ids=[transcripts.id, rubric.id],   # reference both uploaded files
)

print(result.text)                          # the model output

delete_file(transcripts.id)                 # remove the uploaded files
delete_file(rubric.id)
chat.delete()                               # remove the conversation
