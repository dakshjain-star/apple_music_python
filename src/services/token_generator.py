"""
Apple Music Developer Token Generator
Generates JWT tokens using Team ID, Key ID, and AuthKey .p8 file
"""

import os
import time
from typing import Optional

import jwt


class TokenGenerator:
    def __init__(self, team_id: str, key_id: str, auth_key_path: str):
        self.team_id = team_id
        self.key_id = key_id
        self.auth_key_path = auth_key_path
        self.private_key: Optional[str] = None
        self.cached_token: Optional[str] = None
        self.token_expiry: Optional[float] = None

    def load_private_key(self) -> str:
        """Load the private key from .p8 file"""
        if self.private_key:
            return self.private_key

        try:
            key_path = os.path.abspath(self.auth_key_path)
            if not os.path.exists(key_path):
                raise FileNotFoundError(f"AuthKey file not found at: {key_path}")
            
            with open(key_path, 'r') as f:
                self.private_key = f.read()
            
            print("✅ Loaded Apple Music private key")
            return self.private_key
        except Exception as e:
            print(f"❌ Error loading private key: {str(e)}")
            raise

    def generate_developer_token(self) -> str:
        """
        Generate a new Apple Music Developer Token
        Token is valid for 6 months (maximum allowed by Apple)
        """
        try:
            # Check if we have a valid cached token
            if self.cached_token and self.token_expiry and time.time() < self.token_expiry:
                print("📦 Using cached developer token")
                return self.cached_token

            private_key = self.load_private_key()

            now = int(time.time())
            # Token valid for 180 days (Apple's maximum)
            expires_in = 180 * 24 * 60 * 60

            payload = {
                "iss": self.team_id,  # Team ID
                "iat": now,           # Issued at
                "exp": now + expires_in  # Expiration
            }

            headers = {
                "alg": "ES256",
                "kid": self.key_id  # Key ID
            }

            token = jwt.encode(
                payload,
                private_key,
                algorithm="ES256",
                headers=headers
            )

            # Cache the token
            self.cached_token = token
            self.token_expiry = (now + expires_in - 3600)  # Refresh 1 hour before expiry

            print("✅ Generated new Apple Music developer token")
            return token
        except Exception as e:
            print(f"❌ Error generating developer token: {str(e)}")
            raise

    def get_token(self) -> str:
        """Get the current developer token (generates if needed)"""
        return self.generate_developer_token()

    def is_token_valid(self) -> bool:
        """Check if the token is valid"""
        return (
            self.cached_token is not None and 
            self.token_expiry is not None and 
            time.time() < self.token_expiry
        )

    def refresh_token(self) -> str:
        """Force refresh the token"""
        self.cached_token = None
        self.token_expiry = None
        return self.generate_developer_token()
