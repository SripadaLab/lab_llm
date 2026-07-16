"""Module 1 - upload two files, then use both in one model response.

Upload a CSV of transcripts and a text rubric, reference both in one request,
and the model applies the rubric to the data.

Run:  ./scripts/run.sh examples/05_files/example.py
"""
from dotenv import load_dotenv
load_dotenv()                              # load .env values into the environment

from openai import OpenAI                  # the OpenAI Python package

client = OpenAI()                          # reads OPENAI_API_KEY from the environment
conversation = client.conversations.create()  # one server-side conversation

with open("data/transcripts.csv", "rb") as f:   # the data
    transcripts = client.files.create(file=f, purpose="user_data")

with open("data/instructions.txt", "rb") as f:  # the rating rubric
    rubric = client.files.create(file=f, purpose="user_data")

response = client.responses.create(        # reference both files by ID
    model="gpt-5.4-mini",                  # which model answers
    conversation=conversation.id,          # attach the shared conversation
    input=[{                               # one user message: files + task
        "role": "user",
        "content": [
            {"type": "input_file", "file_id": transcripts.id},  # the CSV
            {"type": "input_file", "file_id": rubric.id},       # the rubric
            {
                "type": "input_text",
                "text": (
                    "Use the instructions file to rate each transcript in the "
                    "CSV for anxiety on a 0-100 scale. Give the id and the score."
                ),
            },
        ],
    }],
)

print(response.output_text)                # the model output

client.files.delete(transcripts.id)        # remove the uploaded files
client.files.delete(rubric.id)
client.conversations.delete(conversation.id)  # remove the conversation
