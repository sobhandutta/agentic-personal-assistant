"""
Orchestrator — the core of the multi-agent system.

Flow:
  1. Build the message list from conversation history + the new user message.
  2. Call the LLM (Anthropic or Ollama) with all four tool definitions.
  3. If the LLM wants to use tools:
       a. Dispatch tool calls — in parallel using ThreadPoolExecutor.
       b. Append assistant + tool-result messages.
       c. Call the LLM again.  Repeat until a final text response is produced.
  4. Return the final text response.

Switch providers by setting LLM_PROVIDER in config.py:
  "anthropic" — uses the Anthropic SDK (claude-sonnet-4-6 by default)
  "openai"    — uses the OpenAI SDK (gpt-4o-mini by default)
  "ollama"    — uses the OpenAI-compatible client pointed at localhost:11434

Architecture diagram:

  run(user_message, gradio_history)
    │
    ├─ memory.to_messages()      → converts Gradio history to API format
    ├─ messages.append(user)     → adds the new question
    │
    ├─ LLM_PROVIDER == "anthropic"    → _run_anthropic(messages)
    └─ LLM_PROVIDER == "openai/ollama" → _run_openai(messages)
            │
            │   ┌─────────────────────────────────────────────┐
            │   │             TOOL-CALLING LOOP               │
            │   │                                             │
            │   │  Call LLM with full message history         │
            │   │        ↓                                    │
            │   │  stop_reason == "tool_use" ?                │
            │   │  finish_reason == "tool_calls" ?            │
            │   │        │ YES                                │
            │   │        ↓                                    │
            │   │  _run_tools_parallel(calls)                 │
            │   │    → ThreadPoolExecutor runs all tools      │
            │   │      at the same time                       │
            │   │    → _dispatch() calls the right agent      │
            │   │    → results collected as they finish       │
            │   │        ↓                                    │
            │   │  Append tool results to messages            │
            │   │        ↓                                    │
            │   │  Loop back → Call LLM again with results   │
            │   │        │ NO (end_turn / stop)               │
            │   │        ↓                                    │
            │   │  Return final text answer to user           │
            │   └─────────────────────────────────────────────┘

Key insight: the LLM never answers from its own knowledge — it is always
forced to call tools first, get real data, then summarise it into a response.
"""

# json — used to parse tool call arguments from OpenAI/Ollama responses (they arrive as JSON strings)
import json
import logging
import time

# anthropic — the official Anthropic Python SDK, used only for the Anthropic provider path
import anthropic

log = logging.getLogger("orchestrator")

_RETRY_DELAYS = [2, 5, 10]  # seconds between retries on 529 overload


def _call_with_retry(fn, *args, **kwargs):
    """Call fn(*args, **kwargs), retrying on 529 overload up to 3 times."""
    for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
        try:
            return fn(*args, **kwargs)
        except anthropic.APIStatusError as e:
            if e.status_code == 529:
                log.warning("Anthropic 529 overloaded (attempt %d/%d), retrying in %ds…",
                            attempt, len(_RETRY_DELAYS), delay)
                time.sleep(delay)
            else:
                raise
    # Final attempt — let the exception propagate if still failing
    return fn(*args, **kwargs)

# ThreadPoolExecutor — runs multiple functions in parallel threads
# as_completed       — lets us process results as soon as each thread finishes
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    ANTHROPIC_API_KEY,      # Secret key to authenticate with the Anthropic API
    LLM_PROVIDER,           # "anthropic", "openai", or "ollama" — set in config.py
    ORCHESTRATOR_MODEL,     # Which model to use (e.g. "claude-sonnet-4-6" or "gpt-4o-mini")
    MAX_AGENT_OUTPUT_CHARS, # Cap on how many characters a sub-agent result can return
    openai_client,          # Pre-built OpenAI client (used when LLM_PROVIDER == "openai")
    ollama_client,          # Pre-built Ollama client — OpenAI SDK pointed at localhost:11434
)

# TOOL_DEFINITIONS       — tool schemas in Anthropic format (input_schema)
# TOOL_DEFINITIONS_OPENAI — tool schemas in OpenAI format (type/function/parameters)
from tools import TOOL_DEFINITIONS, TOOL_DEFINITIONS_OPENAI

# The four sub-agents — each knows how to query one data source
from agents import SQLiteAgent, PortfolioAgent, DriveAgent, GmailAgent, KnowledgeBaseAgent

# ConversationMemory — converts Gradio chat history into the API message format
from memory import ConversationMemory

# The system prompt tells the LLM who it is and what tools it has.
# This is sent on every API call as the "system" role — it sets the model's behaviour.
# The leading \ prevents a blank first line in the string.
_SYSTEM_PROMPT = """\
You are a personal AI assistant for Sobhan Dutta and your name is Sobhan. You have access to four data sources via tools:

• query_sqlite    — personal database (profile, skills, work history, projects, education)
• query_portfolio — live portfolio website (professional bio, UX/UI experience, about section)
• query_drive     — Google Drive documents (CV, portfolio, cover letters, notes)
• query_gmail     — Gmail inbox (recent emails, job offers, interview invites)

When answering:
- Act as you are Sobhan Dutta and question is directed to you.
- Choose the most relevant tool(s). Call multiple in parallel when the question spans sources.
- Always say which source(s) you used at the end of your answer (e.g. "Source: SQLite, Portfolio").
- If a tool returns an error or "not connected", answer from whatever sources are available.
- Be concise and conversational.\
"""


class Orchestrator:

    def __init__(self):
        # Pick the right LLM client based on LLM_PROVIDER set in config.py.
        # All three providers are used through self.client later, so the rest
        # of the code doesn't need to care which one was chosen.
        if LLM_PROVIDER == "anthropic":
            # Anthropic has its own SDK with a different interface to OpenAI
            self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        elif LLM_PROVIDER == "openai":
            # Standard OpenAI SDK — talks to api.openai.com
            self.client = openai_client
        else:
            # Ollama also uses the OpenAI SDK but pointed at http://localhost:11434/v1
            # so models run locally on your machine with no API key needed
            self.client = ollama_client

        # ConversationMemory converts Gradio's chat history format into
        # the API's expected message format on each request
        self.memory = ConversationMemory()

        # A lookup dict mapping tool names → agent instances.
        # When the LLM says "call query_sqlite", we use this dict to find
        # which agent object handles that tool.
        self._agents = {
            "query_sqlite":         SQLiteAgent(),          # queries the personal SQLite database
            "query_portfolio":      PortfolioAgent(),       # scrapes the portfolio website
            "query_drive":          DriveAgent(),           # reads Google Drive documents
            "query_gmail":          GmailAgent(),           # searches Gmail inbox
            "query_knowledge_base": KnowledgeBaseAgent(),  # RAG: semantic search over knowledge base docs
        }

    def _dispatch(self, tool_name: str, tool_input: dict) -> str:
        agent = self._agents.get(tool_name)
        if agent is None:
            log.warning("LLM requested unknown tool: %s", tool_name)
            return f"Unknown tool: {tool_name}"

        question = tool_input.get("question", "")
        log.debug("TOOL %s | question: %s", tool_name, question)
        try:
            result = agent.run(question)
            log.debug("TOOL %s | result (%d chars): %s", tool_name, len(result), result[:300])
            return result[:MAX_AGENT_OUTPUT_CHARS]
        except Exception:
            log.exception("TOOL %s raised an unhandled exception", tool_name)
            raise

    def _run_tools_parallel(self, calls: list[tuple[str, str, dict]]) -> list[tuple[str, str]]:
        # `calls` is a list of tuples. Each tuple has 3 items:
        #   - call_id    : unique ID for this tool call e.g. "toolu_01XYZ"
        #   - name       : tool to run e.g. "query_sqlite"
        #   - input_dict : arguments to pass e.g. {"question": "Who is Sobhan?"}
        #
        # Return type list[tuple[str,str]] means we return (call_id, result) pairs
        # so the caller can match each result back to the right tool call.

        # A dict to collect results as they finish: { call_id: result_string }
        results = {}

        # ThreadPoolExecutor runs multiple functions at the same time in parallel threads.
        # max_workers=len(calls) creates one thread per tool call, so if Claude wants
        # to call query_sqlite AND query_drive, both run simultaneously — not one after another.
        with ThreadPoolExecutor(max_workers=len(calls)) as executor:

            # Submit all tool calls to the thread pool at once.
            # executor.submit(fn, arg1, arg2) schedules fn(arg1, arg2) in a background thread
            # and immediately returns a "Future" — a placeholder for the result that isn't ready yet.
            #
            # We build a dict { Future: call_id } so when a Future finishes,
            # we can look up which call_id it belongs to.
            futures = {
                executor.submit(self._dispatch, name, input_dict): call_id
                for call_id, name, input_dict in calls
            }

            # as_completed() yields each Future the moment it finishes (not in submission order).
            # Example: if query_sqlite takes 1s and query_drive takes 3s,
            # we process query_sqlite's result immediately without waiting for query_drive.
            for future in as_completed(futures):

                # Look up which call_id this finished Future belongs to.
                call_id = futures[future]

                try:
                    # future.result() retrieves the return value from _dispatch().
                    # If the thread raised an exception, calling .result() re-raises it here.
                    results[call_id] = future.result()

                except Exception as e:
                    log.exception("Tool thread raised exception for call_id=%s", call_id)
                    results[call_id] = f"[Tool execution error] {e}"

        # Convert { call_id: result } dict into a list of (call_id, result) tuples
        # so the caller can loop over them easily with: for call_id, result in tool_results
        return list(results.items())

    def run(self, user_message: str, gradio_history: list) -> str:
        messages = self.memory.to_messages(gradio_history)
        messages.append({"role": "user", "content": user_message})
        log.info("run() | history_turns=%d", len(messages) - 1)

        try:
            if LLM_PROVIDER == "anthropic":
                return self._run_anthropic(messages)
            else:
                return self._run_openai(messages)
        except anthropic.APIStatusError as e:
            if e.status_code == 529:
                log.error("Anthropic API still overloaded after all retries: %s", e)
                return "⚠️ The AI service is temporarily overloaded. Please try again in a moment."
            log.exception("Anthropic API error (status %s)", e.status_code)
            return f"⚠️ API error ({e.status_code}). Please try again."
        except Exception:
            log.exception("Unexpected error in orchestrator.run()")
            return "⚠️ An unexpected error occurred. Check app.log for details."

    # ── Anthropic path ────────────────────────────────────────────────────────

    def _run_anthropic(self, messages: list) -> str:
        # This is a loop because the conversation may go through multiple rounds:
        #   Round 1: LLM decides to call tools → we run tools → send results back
        #   Round 2: LLM reads tool results → writes final answer → loop ends
        while True:
            # Send the full conversation (system prompt + all messages) to Claude.
            # tools= tells Claude which tools are available to call.
            response = _call_with_retry(
                self.client.messages.create,
                model=ORCHESTRATOR_MODEL,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            log.debug("LLM response | stop_reason=%s | usage=%s", response.stop_reason, response.usage)

            # "end_turn" means Claude has finished and produced a final text answer.
            # No more tool calls — we can return the response to the user.
            if response.stop_reason == "end_turn":
                log.info("LLM end_turn — returning final answer")

                # response.content is a list of content blocks.
                # We scan for the first block that has a .text attribute (the text block).
                # next(..., "No response generated.") provides a fallback if none is found.
                return next(
                    (block.text for block in response.content if hasattr(block, "text")),
                    "No response generated.",
                )

            # "tool_use" means Claude wants to call one or more tools before answering.
            # We need to: run the tools, give Claude the results, then call Claude again.
            if response.stop_reason == "tool_use":

                # Claude's response may contain multiple content blocks (text + tool calls).
                # Filter to only the tool_use blocks — these are the tools Claude wants to call.
                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

                # Extract the three things we need from each tool call:
                #   b.id    — unique ID so we can match the result back to this call later
                #   b.name  — which tool to run, e.g. "query_sqlite"
                #   b.input — the arguments Claude wants to pass, e.g. {"question": "Who is Sobhan?"}
                calls = [(b.id, b.name, b.input) for b in tool_use_blocks]

                # Add Claude's full response (including the tool_use blocks) to the conversation
                # history as an "assistant" turn. The API requires this before we can send tool results.
                messages.append({"role": "assistant", "content": response.content})

                log.info("LLM tool_use | tools=%s", [name for _, name, _ in calls])

                tool_results = self._run_tools_parallel(calls)

                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": cid, "content": result}
                        for cid, result in tool_results
                    ],
                })

                log.debug("Tool results appended | %s", [(cid, r[:120]) for cid, r in tool_results])

            else:
                log.error("Unexpected stop_reason: %s", response.stop_reason)
                return "Unexpected stop reason. Please try again."

    # ── Ollama / OpenAI-compatible path ───────────────────────────────────────

    def _run_openai(self, messages: list) -> str:
        # OpenAI format puts the system prompt inside the messages list
        # as the very first message with role "system" — unlike Anthropic
        # which takes it as a separate `system=` parameter.
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}] + messages

        # Track whether any tool has been called yet.
        # On the first call we set tool_choice="required" to force the model
        # to use tools (otherwise gpt-4o-mini may answer from its own knowledge).
        # After tools have run, we switch to "auto" so the model can freely
        # write a final text answer without being forced to call more tools.
        tools_used = False

        # Same loop concept as _run_anthropic: keep calling the LLM until
        # it produces a final text response with no more tool calls.
        while True:
            response = self.client.chat.completions.create(
                model=ORCHESTRATOR_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS_OPENAI,               # OpenAI-format tool schemas
                tool_choice="auto" if tools_used else "required",  # force tools on first call
            )

            # OpenAI wraps responses in a "choices" list.
            # We always take choices[0] — there's only one since we didn't request multiple.
            choice = response.choices[0]

            log.debug("LLM response | finish_reason=%s", choice.finish_reason)

            if choice.message.tool_calls:
                tools_used = True
                tool_calls = choice.message.tool_calls
                calls = [
                    (tc.id, tc.function.name, json.loads(tc.function.arguments))
                    for tc in tool_calls
                ]
                log.info("LLM tool_use | tools=%s", [name for _, name, _ in calls])

                # Append the assistant's message (with tool_calls) to conversation history.
                # OpenAI requires this before tool result messages can be added.
                # content may be None if the model produced no text alongside the tool calls.
                messages.append({
                    "role": "assistant",
                    "content": choice.message.content,  # text content (often None here)
                    "tool_calls": tool_calls,            # the structured tool call objects
                })

                # Run all tools in parallel and append each result as a separate "tool" message.
                # Unlike Anthropic (which bundles all results in one "user" message),
                # OpenAI expects one "tool" role message per tool call.
                for call_id, result in self._run_tools_parallel(calls):
                    messages.append({
                        "role": "tool",          # special role for tool results in OpenAI format
                        "tool_call_id": call_id, # links this result to the specific tool call above
                        "content": result,       # the actual result string from the sub-agent
                    })

            # If there are no tool calls and the model has finished, return the text answer.
            elif choice.finish_reason in ("stop", "end_turn"):
                # choice.message.content is the final text answer from the LLM.
                # "or" provides a fallback in case content is None or empty.
                return choice.message.content or "No response generated."

            else:
                log.error("Unexpected finish_reason: %s", choice.finish_reason)
                return "Unexpected finish reason. Please try again."
