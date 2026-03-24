import os
import json
import hashlib
import secrets
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

import requests


TOKEN_DIR = os.path.expanduser("~/.youtubeautomation/tokens")


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth redirect callback."""

    auth_code = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        OAuthCallbackHandler.auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h1>Authorization successful!</h1>"
            b"<p>You can close this window.</p></body></html>"
        )

    def log_message(self, format, *args):
        pass  # Suppress server logs


class OAuthManager:
    def __init__(self):
        os.makedirs(TOKEN_DIR, exist_ok=True)

    def get_tokens(self, platform: str) -> dict | None:
        token_file = os.path.join(TOKEN_DIR, f"{platform}.json")
        if os.path.exists(token_file):
            with open(token_file) as f:
                return json.load(f)
        return None

    def save_tokens(self, platform: str, tokens: dict):
        token_file = os.path.join(TOKEN_DIR, f"{platform}.json")
        with open(token_file, "w") as f:
            json.dump(tokens, f, indent=2)

    def authorize(
        self,
        platform: str,
        client_id: str,
        client_secret: str,
        auth_url: str,
        token_url: str,
        scopes: list[str],
        redirect_port: int = 8765,
        use_pkce: bool = False,
        extra_params: dict = None,
    ) -> dict:
        redirect_uri = f"http://localhost:{redirect_port}/callback"

        # Build authorization URL
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
        }
        if extra_params:
            params.update(extra_params)

        code_verifier = None
        if use_pkce:
            code_verifier = secrets.token_urlsafe(64)
            code_challenge = hashlib.sha256(code_verifier.encode()).digest()
            import base64

            code_challenge = (
                base64.urlsafe_b64encode(code_challenge).rstrip(b"=").decode()
            )
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        full_auth_url = f"{auth_url}?{urllib.parse.urlencode(params)}"

        # Start local server for callback
        OAuthCallbackHandler.auth_code = None
        server = HTTPServer(("localhost", redirect_port), OAuthCallbackHandler)
        server_thread = Thread(target=server.handle_request, daemon=True)
        server_thread.start()

        print(f"\nOpening browser for {platform} authorization...")
        print(f"If browser doesn't open, visit:\n{full_auth_url}\n")
        webbrowser.open(full_auth_url)

        # Wait for callback
        server_thread.join(timeout=120)
        server.server_close()

        if not OAuthCallbackHandler.auth_code:
            raise TimeoutError("Authorization timed out - no callback received")

        # Exchange code for tokens
        token_data = {
            "grant_type": "authorization_code",
            "code": OAuthCallbackHandler.auth_code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if code_verifier:
            token_data["code_verifier"] = code_verifier

        resp = requests.post(token_url, data=token_data)
        resp.raise_for_status()
        tokens = resp.json()

        self.save_tokens(platform, tokens)
        print(f"Authorization successful for {platform}!")
        return tokens

    def refresh_token(
        self,
        platform: str,
        client_id: str,
        client_secret: str,
        token_url: str,
    ) -> dict:
        tokens = self.get_tokens(platform)
        if not tokens or "refresh_token" not in tokens:
            raise ValueError(f"No refresh token found for {platform}. Re-authorize.")

        resp = requests.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        resp.raise_for_status()
        new_tokens = resp.json()

        # Preserve refresh token if not returned
        if "refresh_token" not in new_tokens:
            new_tokens["refresh_token"] = tokens["refresh_token"]

        self.save_tokens(platform, new_tokens)
        return new_tokens
