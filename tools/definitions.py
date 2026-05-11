"""Tool schemas for the orchestrator's function-calling loop.

What is a "tool schema"?
  When you give an LLM access to tools (functions), you must describe each tool
  in a structured format so the LLM knows:
    1. What the tool is called  (name)
    2. When to use it           (description)
    3. What arguments to pass   (input_schema / parameters)

  The LLM reads these schemas and decides on its own which tool(s) to call
  and what question to pass as the argument. We never hardcode which tool
  to use — the LLM figures that out from the descriptions.

Two formats are defined here because different LLM providers expect different structures:
  - TOOL_DEFINITIONS        — Anthropic SDK format  (uses "input_schema")
  - TOOL_DEFINITIONS_OPENAI — OpenAI-compatible format (uses "type/function/parameters")

The OpenAI format is auto-generated from the Anthropic format at the bottom of this file,
so you only need to maintain one set of tool definitions.
"""

# TOOL_DEFINITIONS is a list of dicts — one dict per tool.
# The Orchestrator passes this list to the Anthropic API in every request.
# Claude reads these schemas to understand what tools it can call.
TOOL_DEFINITIONS = [

    # ── Tool 1: query_sqlite ──────────────────────────────────────────────────
    {
        # "name" must exactly match the key in Orchestrator._agents dict
        # and the function name the LLM will use when it decides to call the tool.
        "name": "query_sqlite",

        # "description" is the most important field — it tells the LLM WHEN to use
        # this tool. A clear, detailed description means the LLM picks the right tool.
        # We list what tables exist so the LLM knows what kind of questions this can answer.
        "description": (
            "Query Sobhan's personal SQLite database. Contains tables for: "
            "profile (key/value facts), skills (name, level, years), "
            "experience (company, role, dates, description), "
            "projects (name, description, tech_stack, url), "
            "education (institution, degree, year). "
            "Use for factual personal information, work history, skills, or projects."
        ),

        # "input_schema" defines what arguments the LLM must provide when calling this tool.
        # This follows JSON Schema format — a standard way to describe the shape of data.
        "input_schema": {

            # "type": "object" means the argument is a Python dict / JSON object
            "type": "object",

            # "properties" lists every field the LLM can fill in
            "properties": {
                "question": {
                    # The LLM will pass a string value for this field
                    "type": "string",
                    # This description helps the LLM understand what to put here
                    "description": "Natural language question, e.g. 'What companies has Sobhan worked at?'",
                }
            },

            # "required" tells the LLM this field is mandatory — it cannot skip it.
            # If the LLM tries to call this tool without a "question", the API will reject it.
            "required": ["question"],
        },
    },

    # ── Tool 2: query_portfolio ───────────────────────────────────────────────
    {
        "name": "query_portfolio",

        # The description tells the LLM this tool scrapes a LIVE website.
        # It lists what content is there so the LLM knows when to prefer this
        # over query_sqlite (e.g. for branding / bio questions).
        "description": (
            "Scrape and query Sobhan's live portfolio website (sobhandutta.myportfolio.com/about). "
            "Contains professional bio, UX/UI experience, skills, leadership background, and about section. "
            "Use for professional background, design expertise, or personal branding questions."
        ),

        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural language question about the portfolio site content.",
                }
            },
            "required": ["question"],
        },
    },

    # ── Tool 3: query_drive ───────────────────────────────────────────────────
    {
        "name": "query_drive",

        # The description steers the LLM toward this tool for document-style questions
        # (CV, cover letters, notes) that wouldn't fit in a structured database.
        # The phrase "wouldn't be in a structured database" helps the LLM distinguish
        # when to use Drive vs SQLite.
        "description": (
            "Read documents from Sobhan's Google Drive, such as CV, YouTube contents, portfolio, "
            "cover letters, or notes. Use when the question needs document content "
            "that wouldn't be in a structured database."
        ),

        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural language question, e.g. 'YouTube contents', 'Summarize my CV' or 'What projects are in my portfolio?'",
                }
            },
            "required": ["question"],
        },
    },

    # ── Tool 4: query_gmail ───────────────────────────────────────────────────
    {
        "name": "query_gmail",

        # The description tells the LLM this tool reads LIVE emails from Gmail.
        # Listing "job offers, interview invites" helps the LLM recognize
        # when a question is email-related and should route here.
        "description": (
            "Search and read emails from Sobhan's Gmail inbox. "
            "Use for questions about recent messages, job offers, interview invites, "
            "or any email-based information."
        ),

        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural language question, e.g. 'Any interview invites this week?'",
                }
            },
            "required": ["question"],
        },
    },

    # ── Tool 5: query_knowledge_base (RAG) ────────────────────────────────────
    {
        "name": "query_knowledge_base",

        # The description tells the LLM this tool uses semantic search (RAG)
        # over pre-indexed documents — different from the other tools which
        # fetch live data. Use it for deep narrative questions about career,
        # design philosophy, leadership style, or expertise that need
        # long-form context rather than structured database records.
        "description": (
            "Search Sobhan's personal knowledge base using semantic similarity (RAG). "
            "Contains detailed narrative documents about: career history at Ataya, Elisity, "
            "Nuance, and early companies; UX design philosophy and approach; frontend "
            "engineering expertise; leadership and team building style; education and background. "
            "Use for in-depth questions about how Sobhan works, thinks, or leads — "
            "questions that need narrative context beyond what's in the structured database."
        ),

        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural language question, e.g. 'What is Sobhan's design philosophy?' or 'How does Sobhan approach team building?'",
                }
            },
            "required": ["question"],
        },
    },
]

# ── OpenAI-compatible format ──────────────────────────────────────────────────
#
# OpenAI and Ollama expect a slightly different structure from Anthropic:
#
#   Anthropic format:                    OpenAI format:
#   {                                    {
#     "name": "query_sqlite",              "type": "function",       ← extra wrapper
#     "description": "...",                "function": {
#     "input_schema": { ... }                "name": "query_sqlite",
#   }                                        "description": "...",
#                                            "parameters": { ... }  ← renamed key
#                                          }
#                                        }
#
# Instead of copy-pasting all 4 tool definitions in a different format,
# we auto-generate the OpenAI list from TOOL_DEFINITIONS using a list comprehension.
# This means if you update a tool above, the OpenAI version updates automatically.
TOOL_DEFINITIONS_OPENAI = [
    {
        # OpenAI requires this "type": "function" wrapper around every tool
        "type": "function",
        "function": {
            # Copy the name and description directly from the Anthropic definition
            "name": tool["name"],
            "description": tool["description"],

            # Rename "input_schema" → "parameters" (the only structural difference)
            # The actual content (type, properties, required) is identical in both formats.
            "parameters": tool["input_schema"],
        },
    }
    # Loop over every tool in TOOL_DEFINITIONS and convert it
    for tool in TOOL_DEFINITIONS
]
