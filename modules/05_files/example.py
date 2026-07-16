"""Module 1 - upload a file, then use it in a model response.

Run:  ./scripts/run.sh modules/05_files/example.py
Needs OPENAI_API_KEY in .env or your shell (see the root README).
"""
from dotenv import load_dotenv
load_dotenv()                              # load .env values into the environment

from openai import OpenAI                  # the OpenAI Python package

client = OpenAI()                          # reads OPENAI_API_KEY from the environment
conversation = client.conversations.create()  # one server-side conversation

with open("data/transcripts.csv", "rb") as document:  # a local file
    uploaded_file = client.files.create(   # upload it once
        file=document,                     # file bytes
        purpose="user_data",              # intended as model input
    )

response = client.responses.create(        # reference it by file ID
    model="gpt-5.4-mini",                  # which model answers
    conversation=conversation.id,          # attach the shared conversation
    input=[{                                # one user message: file + task
        "role": "user",
        "content": [
            {"type": "input_file", "file_id": uploaded_file.id},  # the file
            {
                "type": "input_text",
                "text": "How many rows are in this file? List its columns.",  # task
            },
        ],
    }],
)

print(response.output_text)                # the model output
client.files.delete(uploaded_file.id)      # remove the server-side file
client.conversations.delete(conversation.id)  # remove the conversation
