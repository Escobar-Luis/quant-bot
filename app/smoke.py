"""Smoke test: one Nicrron call, traced into PRISM. Prints key names, never values.

Run: uv run python smoke.py
Then: uv run python -m prismtrace.verify
"""
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI
from prismtrace import PRISMtrace

load_dotenv()

REQUIRED = ["NICRRON_API_KEY", "PRISMTRACE_API_KEY", "PRISMTRACE_PROJECT_ID"]
missing = [k for k in REQUIRED if not os.getenv(k)]
for k in REQUIRED:
    print(f"{k}: {'set' if os.getenv(k) else 'MISSING'}")
if missing:
    sys.exit("Fill app/.env first (see .env.example).")

model = os.getenv("NICRRON_MODEL", "nicrron/auto")
llm = OpenAI(base_url=os.getenv("NICRRON_BASE_URL", "https://api.nicrron.ai/v1"),
             api_key=os.environ["NICRRON_API_KEY"])
pt = PRISMtrace(api_key=os.environ["PRISMTRACE_API_KEY"],
                host=os.getenv("PRISMTRACE_HOST", "https://api.prism.blockconvey.com"),
                project_id=os.environ["PRISMTRACE_PROJECT_ID"])

messages = [{"role": "user", "content": "Hello, MONEY TALKS! Reply in five words."}]
start = time.monotonic()
reply = llm.chat.completions.create(model=model, messages=messages)
latency_ms = int((time.monotonic() - start) * 1000)
text = reply.choices[0].message.content
usage = reply.usage

print(f"NICRRON OK: model={reply.model} latency={latency_ms}ms reply={text!r}")

session_id = f"smoke-{int(time.time())}"
pt.trace_llm(
    model=reply.model or model,
    input_messages=messages,
    output=text or "",
    latency_ms=latency_ms,
    token_count_input=getattr(usage, "prompt_tokens", 0) or 0,
    token_count_output=getattr(usage, "completion_tokens", 0) or 0,
    agent_id="quant-bot-smoke",
    agent_name="quant-bot smoke test",
    session_id=session_id,
)
# An agent run with steps, so it shows on PRISM's Agent Runs page.
run = pt.submit_trajectory(
    agent_id="quant-bot-smoke",
    agent_name="quant-bot smoke test",
    conversation_id=session_id,
    model=reply.model or model,
    steps=[{"step_type": "final_answer", "label": "reply", "input_summary": messages[0]["content"],
            "output_summary": text or "", "duration_ms": latency_ms}],
)
pt.flush(timeout=30)
pt.close()
print(f"PRISM trace sent; agent run {'id=' + str(run.get('id')) if run else 'FAILED (see warning above)'}.")
print("Next: uv run python -m prismtrace.verify")
