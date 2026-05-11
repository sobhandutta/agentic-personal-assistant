"""
Google OAuth2 helper shared by DriveAgent and GmailAgent.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THE TWO CREDENTIAL FILES — what they are and why they exist
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. auth/credentials/client_secret.json
   ─────────────────────────────────────
   WHO:    Identifies YOUR APPLICATION to Google.
   WHAT:   Contains client_id, client_secret, project_id, auth_uri, token_uri,
           redirect_uris.
   WHERE:  Downloaded from Google Cloud Console when you create OAuth credentials.
   WHEN:   Read once during the first-time login flow (never changes).
   THINK:  Like your app's "username + password" with Google — proves to Google
           that this is your registered application, not someone else's.

2. auth/credentials/token.json
   ────────────────────────────
   WHO:    Identifies the LOGGED-IN USER (you) to Google.
   WHAT:   Contains token, refresh_token, token_uri, client_id, client_secret,
           scopes, expiry.
   WHERE:  Auto-created by this script after the user logs in via browser.
   WHEN:   Loaded on every request. The access token expires after ~1 hour but
           the refresh_token never expires — so Google silently issues a new
           access token without asking you to log in again.
   THINK:  Like a session cookie — proves to Google that you already logged in
           and gave permission to access Drive and Gmail.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THE OAUTH FLOW — what happens the first time
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Step 1: App reads client_secret.json  →  knows who it is
  Step 2: App opens a browser window    →  Google login page
  Step 3: You log in & click "Allow"    →  you grant Drive + Gmail access
  Step 4: Google returns a token        →  saved as token.json on disk
  Step 5: App uses token.json           →  all future API calls work silently

After Step 4, the browser flow never happens again (unless you delete token.json).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FIRST-TIME SETUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Go to https://console.cloud.google.com/
  2. Create a project → enable Drive API + Gmail API
  3. Create OAuth2 credentials (Desktop App) → download as client_secret.json
  4. Place client_secret.json in auth/credentials/
  5. Run:  python auth/google_auth.py
     A browser window opens → log in → token.json is saved automatically.

Subsequent runs use the cached token.json (refreshed silently when expired).
"""

import os

# Credentials — represents a set of Google OAuth2 credentials (the token)
from google.oauth2.credentials import Credentials

# Request — used to make an HTTP request to Google's token endpoint to refresh expired tokens
from google.auth.transport.requests import Request

# InstalledAppFlow — handles the OAuth2 browser login flow for desktop applications
# "Installed" means running locally on your machine (vs a web server)
from google_auth_oauthlib.flow import InstalledAppFlow

# GOOGLE_CREDENTIALS_PATH — path to client_secret.json (your app's identity)
# GOOGLE_TOKEN_PATH        — path to token.json        (your login session)
# GOOGLE_SCOPES            — list of permissions requested from Google
#                            e.g. drive.readonly, gmail.readonly
from config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH, GOOGLE_SCOPES


def get_google_credentials() -> Credentials | None:
    """
    Return valid Google OAuth2 credentials, refreshing or re-authorising as needed.
    Returns None if client_secret.json is missing (agents degrade gracefully).
    """

    # If client_secret.json doesn't exist, we can't authenticate at all.
    # Return None so DriveAgent and GmailAgent can show a helpful error message
    # instead of crashing the whole application.
    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        return None

    # Start with no credentials — we'll load or create them below.
    creds = None

    # ── Try to load existing credentials from token.json ─────────────────────
    if os.path.exists(GOOGLE_TOKEN_PATH):
        # Load the saved token from disk. This avoids a browser login on every run.
        # from_authorized_user_file() reads the JSON and reconstructs the Credentials object.
        # GOOGLE_SCOPES is passed so the library can verify the token covers the right permissions.
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_PATH, GOOGLE_SCOPES)

    # ── Check if credentials are valid; refresh or re-login if not ───────────
    if not creds or not creds.valid:
        # creds.expired — the 1-hour access token has timed out
        # creds.refresh_token — we have a long-lived token to get a new access token silently
        if creds and creds.expired and creds.refresh_token:
            # Silent refresh: ask Google for a new access token using the refresh token.
            # No browser window — this happens in the background automatically.
            # Request() provides the HTTP transport layer for the refresh call.
            creds.refresh(Request())

        else:
            # No valid credentials and no refresh token — must do the full browser login.
            # This happens only the very first time (or if token.json was deleted).
            # InstalledAppFlow reads client_secret.json to know which app is requesting access.
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_PATH, GOOGLE_SCOPES
            )

            # Opens a browser window → Google login page → you click "Allow"
            # port=0 means the OS picks any available free port for the redirect URL.
            # After login, creds contains the new access token + refresh token.
            creds = flow.run_local_server(port=0)

        # Save the new/refreshed credentials to token.json so the next run
        # can load them directly without going through the browser login again.
        with open(GOOGLE_TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    # Return the valid credentials — DriveAgent and GmailAgent use this to
    # authenticate all their Google API calls.
    return creds


# ── Run this file directly to do first-time authentication ───────────────────
# Usage:  python auth/google_auth.py
#
# When run as a script (not imported), __name__ == "__main__" is True.
# This lets us use this file both as a module (imported by agents) AND
# as a standalone setup script (run directly by the user).
if __name__ == "__main__":
    creds = get_google_credentials()
    if creds:
        print("Authentication successful. token.json saved.")
    else:
        print("client_secret.json not found. See docstring for setup instructions.")
