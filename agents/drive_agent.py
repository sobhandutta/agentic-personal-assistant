# anthropic — the Anthropic SDK used to call the Claude LLM
import anthropic

# googleapiclient.discovery.build — Google's official Python client library.
# build() creates a service object to interact with a specific Google API (Drive, Gmail, etc.)
from googleapiclient.discovery import build

# BaseAgent — the abstract base class that enforces every agent has a run(question) method
from .base_agent import BaseAgent

# GOOGLE_DRIVE_FOLDER_ID  — optional env var: skip folder lookup if the ID is already known
# DRIVE_NOTES_FOLDER_NAME — the name of the Google Drive folder to search in (e.g. "LLM Project Notes")
# SUBAGENT_MODEL          — the Claude model used by sub-agents (haiku — fast and cheap)
from config import GOOGLE_DRIVE_FOLDER_ID, DRIVE_NOTES_FOLDER_NAME, SUBAGENT_MODEL

# get_google_credentials — our own helper that loads the saved OAuth token
# so we can authenticate with Google without asking the user to log in every time.
from auth.google_auth import get_google_credentials

# The MIME type string Google uses internally to represent a Drive folder.
# MIME types identify file/folder formats. We use this when searching for folders by type.
_FOLDER_MIME = "application/vnd.google-apps.folder"


def _escape_drive_query_string(value: str) -> str:
    # Google Drive API queries use a specific query language (like SQL).
    # If the folder name contains backslashes or single quotes, they would
    # break the query syntax. This function escapes them so the query stays valid.
    #
    # Example without escaping:  name = 'Sobhan's Notes'  ← broken (unmatched quote)
    # Example with escaping:     name = 'Sobhan\'s Notes' ← valid
    #
    # Step 1: escape any backslashes first (\ → \\)
    # Step 2: escape any single quotes   (' → \')
    # Order matters: always escape backslashes before single quotes.
    return value.replace("\\", "\\\\").replace("'", "\\'")


# System prompt for the final answer step.
# "solely on the provided document excerpts" prevents Claude from hallucinating —
# it must only use the real content we fetched from Drive.
# "Cite the document name" helps the user know which file the answer came from.
_SYSTEM_PROMPT = """You are a document assistant. Answer the user's question based solely on the
provided Google Drive document excerpts. Cite the document name when relevant."""

# The MIME type for a native Google Doc (created inside Google Docs).
# These require a special "export" API call to convert to plain text.
# Regular files (PDFs, .txt, .docx) use a different "get_media" API call.
_GOOGLE_DOC_MIME = "application/vnd.google-apps.document"

# The format we want to export Google Docs as — plain text is easiest for Claude to read.
_EXPORT_MIME = "text/plain"

# Maximum characters to read per file. Documents can be very long (e.g. a full CV).
# We truncate to avoid overflowing the LLM's context window.
_MAX_FILE_CHARS = 2000

# Maximum number of files to read from the Drive folder.
# Reading too many files would make the combined text too long for Claude.
_MAX_FILES = 4


class DriveAgent(BaseAgent):
    """Reads Google Drive documents and answers questions from their content."""

    def __init__(self):
        # Create the Anthropic client for calling Claude.
        # It automatically reads ANTHROPIC_API_KEY from the environment.
        self.client = anthropic.Anthropic()

        # The Drive API service object — None until first use.
        # Lazy initialisation: only created when actually needed, then cached for reuse.
        self._service = None

    def _get_service(self):
        # Only create the Drive API service once (lazy init / caching pattern).
        # On subsequent calls, we return the already-created service immediately.
        if self._service is None:
            # Load the saved Google OAuth credentials (token) from disk.
            creds = get_google_credentials()

            # If credentials are missing (user hasn't authenticated yet), return None.
            # The caller will show a helpful message asking them to run google_auth.py.
            if creds is None:
                return None

            # build() creates the Drive API client.
            # "drive" = Google Drive API, "v3" = API version, credentials = our OAuth token.
            self._service = build("drive", "v3", credentials=creds)

        return self._service

    def _resolve_notes_folder_id(self, service) -> str | None:
        # We need the folder ID to list files inside it.
        # There are two ways to get it:
        #   Option A (fast): user already set GOOGLE_DRIVE_FOLDER_ID in .env
        #   Option B (search): look up the folder by name via the Drive API

        # Option A: if the folder ID is already configured, use it directly.
        # This skips the API search call and is faster.
        if GOOGLE_DRIVE_FOLDER_ID:
            return GOOGLE_DRIVE_FOLDER_ID

        # Option B: search Drive for a folder with the configured name.
        # Build a Drive API query string (similar to SQL WHERE clause).
        #   name = '...'           → match by folder name
        #   mimeType = '...'       → only match folders (not files)
        #   trashed = false        → skip deleted items
        q = (
            f"name = '{_escape_drive_query_string(DRIVE_NOTES_FOLDER_NAME)}' "
            f"and mimeType = '{_FOLDER_MIME}' and trashed = false"
        )

        # Execute the search. pageSize=5 means return up to 5 matching folders.
        # fields="files(id, name)" tells Google to only return id and name — saves bandwidth.
        result = (
            service.files()
            .list(q=q, pageSize=5, fields="files(id, name)")
            .execute()
        )

        # result is a dict like: {"files": [{"id": "...", "name": "LLM Project Notes"}, ...]}
        # .get("files", []) safely returns an empty list if no folders were found.
        folders = result.get("files", [])

        # If no folder was found, return None — the caller will show a helpful error.
        if not folders:
            return None

        # Return the ID of the first matching folder.
        # If multiple folders share the same name, we take the first one.
        return folders[0]["id"]

    def _list_files(self, service, folder_id: str) -> list[dict]:
        # List all files inside the specified folder.
        # Build a Drive query: find all files whose parent is this folder and aren't trashed.
        # '{folder_id}' in parents → file is directly inside this folder
        q = f"'{folder_id}' in parents and trashed = false"

        result = (
            service.files()
            .list(
                q=q,
                pageSize=_MAX_FILES,                    # limit to _MAX_FILES results
                fields="files(id, name, mimeType)"      # only fetch id, name, and MIME type
            )
            .execute()
        )

        # Return the list of file dicts, or an empty list if the folder is empty.
        return result.get("files", [])

    def _read_file(self, service, file_id: str, mime_type: str) -> str:
        # Read the content of a single file from Drive.
        # The approach differs depending on whether it's a native Google Doc or a regular file.

        if mime_type == _GOOGLE_DOC_MIME:
            # Native Google Docs cannot be downloaded directly — they exist only inside Google.
            # We must "export" them, which converts the Google Doc to a downloadable format.
            # mimeType=_EXPORT_MIME tells Google to convert it to plain text before sending.
            content = service.files().export(fileId=file_id, mimeType=_EXPORT_MIME).execute()
        else:
            # Regular files (PDFs, .txt, .docx, etc.) can be downloaded directly.
            # get_media() returns the raw file bytes.
            content = service.files().get_media(fileId=file_id).execute()

        # content is a bytes object. Decode it to a UTF-8 string.
        # errors="ignore" skips any bytes that can't be decoded (e.g. binary data in PDFs).
        # [:_MAX_FILE_CHARS] truncates to avoid sending enormous documents to Claude.
        return content.decode("utf-8", errors="ignore")[:_MAX_FILE_CHARS]

    def run(self, question: str) -> str:
        # This is the main entry point called by the Orchestrator.
        # Full flow: authenticate → find folder → list files → read files → ask Claude → return answer.

        # Step 1: Get (or create) the authenticated Drive API service.
        service = self._get_service()

        # If authentication failed or hasn't been done, return a helpful error message.
        if service is None:
            return (
                "[DriveAgent] Google Drive not connected. "
                "Run `python auth/google_auth.py` to authenticate."
            )

        try:
            # Step 2: Find the ID of the configured Drive folder (by name or from .env).
            folder_id = self._resolve_notes_folder_id(service)

            # If the folder doesn't exist in Drive, tell the user how to fix it.
            if folder_id is None:
                return (
                    f"[DriveAgent] Could not find a Drive folder named "
                    f"'{DRIVE_NOTES_FOLDER_NAME}'. Create it in Drive, or set "
                    "GOOGLE_DRIVE_FOLDER_ID in .env to the folder's ID (from the Drive URL)."
                )

            # Step 3: List files inside that folder (up to _MAX_FILES).
            files = self._list_files(service, folder_id)

            # If the folder exists but is empty, return a helpful message.
            if not files:
                return (
                    f"[DriveAgent] No files inside folder '{DRIVE_NOTES_FOLDER_NAME}' "
                    "(add Google Docs or other files there)."
                )

            # Step 4: Read the content of each file and build a list of excerpts.
            excerpts = []
            for f in files:
                try:
                    # Read this file's content (auto-handles Google Docs vs regular files).
                    text = self._read_file(service, f["id"], f["mimeType"])

                    # Wrap the text with the file name as a header so Claude knows
                    # which document each excerpt came from. The system prompt tells
                    # Claude to cite document names in its answer.
                    excerpts.append(f"--- {f['name']} ---\n{text}")

                except Exception:
                    # If one file fails (permission denied, corrupt file, etc.),
                    # silently skip it and continue reading the other files.
                    pass

            # If every file failed to read, return an error.
            if not excerpts:
                return "[DriveAgent] Could not read any Drive files."

            # Step 5: Join all excerpts into one big string with blank lines between documents.
            # This is what we'll pass to Claude as the "document context".
            combined = "\n\n".join(excerpts)

            # Step 6: Call Claude (the LLM) with the document excerpts + the user's question.
            # Claude reads the documents and answers the question based solely on their content.
            response = self.client.messages.create(
                model=SUBAGENT_MODEL,
                max_tokens=1024,         # enough for a detailed answer from multiple documents
                system=_SYSTEM_PROMPT,   # tells Claude to only use the provided document content
                messages=[
                    {
                        "role": "user",
                        # Inject both the document excerpts and the question.
                        # Claude reads everything above "Question:" as context.
                        "content": f"Documents:\n{combined}\n\nQuestion: {question}",
                    }
                ],
            )

            # Return Claude's plain text answer back to the Orchestrator.
            return response.content[0].text

        except Exception as e:
            # Catch any unexpected error (API failure, network issue, auth expiry, etc.)
            # and return an error string so the rest of the application keeps running.
            return f"[DriveAgent error] {e}"
