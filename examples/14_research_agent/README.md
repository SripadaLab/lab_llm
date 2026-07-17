# Study Investigator

An open-ended, multi-turn research agent.

The agent explores one fixed synthetic study. It chooses which files to read,
uses hosted Python for calculations, and cites the evidence behind its answers.
Different questions can produce different investigation paths.

```bash
./scripts/run.sh examples/14_research_agent/example.py
```

Try:

- `Is this study ready for analysis?`
- `Which participants can be analyzed safely?`
- `Do the protocol and item bank agree?`
- `Use Python to check the ratings and summarize anything impossible.`
- `What should the research team fix first?`

`study_files.py` enforces read-only access to the fixed `study/` folder.
`study_tools.py` exposes that access to the agent. Code Interpreter runs in an
OpenAI-hosted sandbox. It does not receive local shell access.

Conversation state lives in an in-process SQLite session. Closing the script
clears the chat.
