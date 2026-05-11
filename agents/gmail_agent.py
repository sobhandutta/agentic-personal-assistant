# base64 — Gmail API returns email body content encoded in Base64.
# We need this to decode it back into readable text.
import base64

# json — used to convert the list of email dicts into a JSON string
# so Claude can read them in a structured, readable format.
import json

# date — used to get today's date so we can tell Claude what "today" is
# when converting relative questions like "any emails this week?" into search queries.
from datetime import date

# anthropic — the Anthropic SDK used to call the Claude LLM (used twice:
# once to build the Gmail search query, once to answer the user's question)
import anthropic

# googleapiclient.discovery.build — Google's official Python client library.
# build() creates a service object to talk to a specific Google API.
from googleapiclient.discovery import build

# BaseAgent — the abstract base class that enforces every agent has a run(question) method
from .base_agent import BaseAgent

# SUBAGENT_MODEL — the Claude model used by sub-agents (haiku — fast and cheap)
from config import SUBAGENT_MODEL

# get_google_credentials — our own helper that loads the saved OAuth token
# so we can authenticate with Google without asking the user to log in every time.
from auth.google_auth import get_google_credentials

# System prompt for the final answer step.
# "solely on the provided email data" prevents Claude from guessing or hallucinating —
# it must only use what we retrieved from Gmail.
_ANSWER_SYSTEM = """You are an email assistant. Answer the user's question based solely on the
provided email data. Be concise and cite sender/subject when relevant."""

# How many emails to fetch per query. Keeping this small avoids overwhelming
# Claude's context window and keeps costs low.
_MAX_EMAILS = 5

# How many characters to extract from each email body.
# Email bodies can be very long (HTML newsletters, threads, etc.).
# We truncate to 400 chars to stay within the LLM context limit.
_MAX_BODY_CHARS = 400


class GmailAgent(BaseAgent):
    """Searches Gmail and answers questions from email content."""

    def __init__(self):
        # Create the Anthropic client for calling Claude.
        # It automatically reads ANTHROPIC_API_KEY from the environment.
        self.client = anthropic.Anthropic()

        # The Gmail API service object — set to None until first use.
        # We use lazy initialisation: create it only when needed, then reuse it.
        self._service = None

    def _get_service(self):
        # Only create the Gmail service once (lazy init / caching pattern).
        # If we already have it, return it immediately without re-authenticating.
        if self._service is None:
            # Load the saved Google OAuth credentials from the token file on disk.
            creds = get_google_credentials()

            # If credentials don't exist (user hasn't authenticated yet), return None.
            # The caller will show a helpful message asking them to run google_auth.py.
            if creds is None:
                return None

            # build() creates the Gmail API client.
            # "gmail" = which Google API, "v1" = API version, credentials = our auth token.
            # This object lets us call Gmail endpoints like list messages, get message, etc.
            self._service = build("gmail", "v1", credentials=creds)

        return self._service

    def _build_query(self, question: str) -> str:
        # This method uses Claude (LLM call #1) to convert the user's natural language
        # question into a Gmail search query string.
        #
        # Example:
        #   question: "Any job offers this week?"
        #   → Claude returns: "subject:offer newer_than:7d"
        #
        # This is smarter than keyword matching — Claude understands intent.

        # Get today's date as a string like "2026-04-26".
        # We inject this into the prompt so Claude knows what "today", "this week",
        # "yesterday" etc. actually mean at the time of the request.
        today = date.today().isoformat()

        system = (
            f"Today's date is {today}. "
            # Tell Claude its job: convert the question to a Gmail search string.
            "Convert the user's question into a Gmail search query string "
            # Give examples of valid Gmail query syntax so Claude knows the format.
            "(e.g. \"from:recruiter subject:offer\", \"newer_than:7d\"). "
            # Instruct to use relative time so the query stays valid over time.
            "Use relative time operators (newer_than:Nd) instead of absolute dates. "
            # We want ONLY the raw query — no explanation, no markdown, no extra text.
            "Return ONLY the raw query string, nothing else. "
            # If Claude can't figure out a query, an empty string means "search everything".
            "If unsure, return an empty string."
        )

        # Call Claude with a tiny max_tokens=64 — Gmail queries are always very short.
        response = self.client.messages.create(
            model=SUBAGENT_MODEL,
            max_tokens=64,
            system=system,
            messages=[{"role": "user", "content": question}],
        )

        # Extract the raw query string and remove any accidental leading/trailing whitespace.
        return response.content[0].text.strip()

    def _get_body(self, payload: dict) -> str:
        # Gmail email bodies arrive in a nested structure and are Base64-encoded.
        # This method extracts and decodes the plain text body from that structure.
        #
        # Emails come in two structures:
        #   Simple:  payload.body.data           (plain email with one part)
        #   Multipart: payload.parts[].body.data  (email with attachments or HTML + text)

        # --- Simple email (single body) ---
        # Check if the body data exists directly on the payload.
        if payload.get("body", {}).get("data"):
            # Gmail encodes body content in URL-safe Base64. Decode it to bytes first.
            raw = base64.urlsafe_b64decode(payload["body"]["data"])
            # Decode bytes to a UTF-8 string. errors="ignore" skips unreadable characters.
            # Truncate to _MAX_BODY_CHARS to avoid sending huge email bodies to Claude.
            return raw.decode("utf-8", errors="ignore")[:_MAX_BODY_CHARS]

        # --- Multipart email (e.g. HTML + plain text + attachments) ---
        # Loop through each part of the email looking for the plain text version.
        for part in payload.get("parts", []):
            # We only want "text/plain" — skip HTML and attachment parts.
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                raw = base64.urlsafe_b64decode(part["body"]["data"])
                return raw.decode("utf-8", errors="ignore")[:_MAX_BODY_CHARS]

        # If no readable body was found in either structure, return empty string.
        return ""

    def _fetch_emails(self, service, query: str) -> list[dict]:
        # Step 1: Search Gmail for matching message IDs.
        # This returns a list of lightweight message objects with just the ID.
        # userId="me" means "the authenticated user's inbox".
        # q=query is the Gmail search string (e.g. "subject:offer newer_than:7d").
        # maxResults=_MAX_EMAILS caps how many we retrieve.
        result = service.users().messages().list(
            userId="me", q=query, maxResults=_MAX_EMAILS
        ).execute()

        emails = []

        # result.get("messages", []) safely returns an empty list if no messages matched.
        for msg in result.get("messages", []):

            # Step 2: Fetch the full email content for each message ID.
            # The list() call above only gives us IDs — we need another API call per email
            # to get headers (subject, from, date) and the body.
            # format="full" returns the complete email including headers and body parts.
            full = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()

            # Headers are returned as a list of {"name": ..., "value": ...} dicts.
            # We convert it to a regular dict for easy lookup: {"Subject": ..., "From": ...}
            headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}

            # Build a clean, compact email dict with just the fields Claude needs.
            # .get(key, "") safely returns empty string if a header is missing.
            emails.append({
                "subject": headers.get("Subject", ""),
                "from":    headers.get("From", ""),
                "date":    headers.get("Date", ""),
                "body":    self._get_body(full["payload"]),  # decoded plain text body
            })

        return emails

    def run(self, question: str) -> str:
        # This is the main entry point called by the Orchestrator.
        # Full flow: authenticate → build query → fetch emails → ask Claude → return answer.

        # Step 1: Get (or create) the authenticated Gmail API service.
        service = self._get_service()

        # If authentication failed or hasn't been done yet, return a helpful error.
        if service is None:
            return (
                "[GmailAgent] Gmail not connected. "
                "Run `python auth/google_auth.py` to authenticate."
            )

        try:
            # Step 2: Use Claude (LLM call #1) to convert the question into a Gmail search query.
            # e.g. "Any interview invites?" → "subject:interview newer_than:14d"
            query = self._build_query(question)

            # Step 3: Search Gmail with the generated query and fetch matching emails.
            emails = self._fetch_emails(service, query)

            # Fallback: if the generated query matched nothing (empty inbox for that query),
            # broaden the search to any email from the last 30 days.
            # This ensures we still give Claude something to work with.
            if not emails:
                emails = self._fetch_emails(service, "newer_than:30d")

            # If there are truly no emails at all, return early with a clear message.
            if not emails:
                return "[GmailAgent] No recent emails found in your inbox."

            # Step 4: Convert the list of email dicts to a formatted JSON string.
            # indent=2 makes it human-readable, which also helps Claude parse it accurately.
            emails_text = json.dumps(emails, indent=2)

            # Step 5: Use Claude (LLM call #2) to read the emails and answer the question.
            # We pass both the raw email data AND the original question in one message.
            response = self.client.messages.create(
                model=SUBAGENT_MODEL,
                max_tokens=1024,         # enough for a detailed answer about several emails
                system=_ANSWER_SYSTEM,   # tells Claude to only use the provided email data
                messages=[
                    {
                        "role": "user",
                        # Inject both the email data and the question into one message.
                        # Claude reads the emails first, then answers the question based on them.
                        "content": f"Emails:\n{emails_text}\n\nQuestion: {question}",
                    }
                ],
            )

            # Return Claude's plain text answer back to the Orchestrator.
            return response.content[0].text

        except Exception as e:
            # Catch any error (API failure, auth expiry, network issue, etc.)
            # and return an error string so the app keeps running.
            return f"[GmailAgent error] {e}"
