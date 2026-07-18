"""De-identify research text locally before sending it to an LLM.

Run:  ./scripts/run.sh examples/15_local_deidentification/example.py
"""
from lab_llm import Deidentifier, call_llm


note = (                                        # synthetic research text
    "Maya Chen called +1 (415) 555-0124 on April 12, 2026. "
    "Email maya.chen@example.com with the follow-up."
)

privacy = Deidentifier(device="cpu")            # the filter runs locally

preview = privacy.deidentify(note)               # detect and mask PII locally
print("\nLOCAL DE-IDENTIFICATION PREVIEW")
print("---------------------------------")
print(preview.preview())                         # inspect what will be replaced

result = call_llm(
    note,                                        # the original local text
    instructions="Summarize this note in one sentence.",
    deidentifier=privacy,                        # filter before the API request
)

print("\n\nLLM RESPONSE")
print("------------")
print(result.text)                               # the model's summary

audit = result.deidentification                  # counts only, no original PII
print("\n\nPRIVACY AUDIT")
print("-------------")
print(f"Texts checked:       {audit.text_count}")
print(f"Identifiers masked:  {audit.identifier_count}")
for label, count in audit.counts_by_label.items():
    print(f"  {label.replace('_', ' ').title()}: {count}")
