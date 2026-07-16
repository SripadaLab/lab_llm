"""Module 1 - the same file call, using lab_llm.

Run:  ./scripts/run.sh modules/05_files/nicer_example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from lab_llm import Conversation, delete_file, upload_file  # reusable helpers

uploaded_file = upload_file("data/transcripts.csv")  # upload once

chat = Conversation()                       # one server-side conversation
result = chat.send(                         # file and prompt in one turn
    "How many rows are in this file? List its columns.",
    file_id=uploaded_file.id,               # reference the uploaded file
)

print(result.text)                          # the model output
delete_file(uploaded_file.id)               # remove the server-side file
chat.delete()                               # remove the conversation
