# requests — a popular Python library for making HTTP requests (fetching web pages)
import requests

# anthropic — the Anthropic SDK used to call the Claude LLM
import anthropic

# BeautifulSoup — a library for parsing HTML and extracting readable text from web pages
from bs4 import BeautifulSoup

# BaseAgent — the abstract base class that enforces every agent has a run(question) method
from .base_agent import BaseAgent

# SUBAGENT_MODEL — the Claude model used by sub-agents (haiku — fast and cheap)
# PORTFOLIO_URL  — the URL of Sobhan's portfolio website, defined in config.py
from config import SUBAGENT_MODEL, PORTFOLIO_URL

# HTTP headers sent with every web request.
# Many websites block requests from scripts (bots). By pretending to be a real
# Chrome browser with a User-Agent header, we avoid being blocked.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    )
}

# Maximum number of characters we pass to Claude from the scraped page.
# Web pages can be very long — we cap at 3000 chars to stay within the
# model's context window and keep costs low.
_MAX_CHARS = 3000

# Instruction given to Claude when it answers questions about the portfolio.
# "solely on the provided content" prevents Claude from mixing in its own
# training knowledge — we want answers from the real website, not guesses.
_SYSTEM_PROMPT = """You are a professional profile assistant. Answer questions concisely based
solely on the provided portfolio website content. If the answer is not in the content, say so."""


def _scrape(url: str) -> str:
    """Fetch a webpage and return its plain text (same approach as brochure-from-web/scraper.py)."""

    # Make an HTTP GET request to the URL, just like a browser would.
    # headers=_HEADERS makes us look like a real Chrome browser.
    # timeout=10 means we give up if the site doesn't respond within 10 seconds.
    response = requests.get(url, headers=_HEADERS, timeout=10)

    # raise_for_status() checks the HTTP status code.
    # If the server returned an error (e.g. 404 Not Found, 500 Server Error),
    # this raises an exception instead of silently returning broken HTML.
    response.raise_for_status()

    # BeautifulSoup parses the raw HTML bytes into a navigable tree structure.
    # "html.parser" is Python's built-in HTML parser — no extra install needed.
    soup = BeautifulSoup(response.content, "html.parser")

    # Remove tags that contain no useful readable text.
    # "script" — JavaScript code
    # "style"  — CSS styling rules
    # "img"    — image tags (no text content)
    # "input"  — form input fields
    # .decompose() removes each tag and its children from the tree entirely.
    for tag in soup(["script", "style", "img", "input"]):
        tag.decompose()

    # Extract the page title (e.g. "Sobhan Dutta — UX Designer").
    # soup.title is the <title> tag; .string gets its text content.
    # If there's no <title> tag, we default to an empty string.
    title = soup.title.string if soup.title else ""

    # Extract all visible text from the <body> of the page.
    # separator="\n" puts each text block on its own line (more readable).
    # strip=True removes extra whitespace from each block.
    # If there's no <body> tag, we default to an empty string.
    body = soup.body.get_text(separator="\n", strip=True) if soup.body else ""

    # Combine title + body into one string, then truncate to _MAX_CHARS.
    # The [:_MAX_CHARS] slice ensures we never send too much text to Claude.
    return (title + "\n\n" + body)[:_MAX_CHARS]


class PortfolioAgent(BaseAgent):
    """Scrapes the portfolio website and answers questions from its content."""

    def __init__(self):
        # Create the Anthropic client.
        # It automatically reads ANTHROPIC_API_KEY from the environment.
        self.client = anthropic.Anthropic()

    def run(self, question: str) -> str:
        # This is the main entry point called by the Orchestrator.
        # Full flow: fetch page → extract text → ask Claude → return answer.
        try:
            # Step 1: Scrape the portfolio website and get its plain text content.
            # This makes a real HTTP request to the live website every time it's called.
            content = _scrape(PORTFOLIO_URL)

            # Step 2: Send the scraped text + the user's question to Claude.
            # Claude reads the content and answers based only on what's in it.
            response = self.client.messages.create(
                model=SUBAGENT_MODEL,
                max_tokens=1024,        # enough for a detailed but concise answer
                system=_SYSTEM_PROMPT,  # tells Claude to only use the provided content
                messages=[{
                    "role": "user",
                    # We inject both the scraped page content AND the question into
                    # one message. Claude reads the content first, then answers the question.
                    "content": f"Portfolio website content:\n{content}\n\nQuestion: {question}",
                }],
            )

            # Step 3: Extract Claude's text answer from the response.
            # response.content is a list of content blocks; [0] is the first (and only) one.
            # .text gives us the plain string answer.
            return response.content[0].text

        except requests.RequestException as e:
            # This catches network-level errors specifically:
            # e.g. no internet, site is down, timeout exceeded, 404/500 errors.
            # We handle this separately so the user gets a clear "site unreachable" message.
            return f"[PortfolioAgent] Could not fetch portfolio site: {e}"

        except Exception as e:
            # Catch-all for any other error (e.g. Anthropic API error, parsing failure).
            # Returning an error string keeps the app running — the Orchestrator
            # can still use results from other agents that succeeded.
            return f"[PortfolioAgent error] {e}"
