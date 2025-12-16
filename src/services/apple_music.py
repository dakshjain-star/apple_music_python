"""
Apple Music Service
Handles all Apple Music API interactions using Developer Token and User Token
Includes logging to trace fetch requests and responses.
"""

from typing import Optional, Dict, Any, List
import httpx


class AppleMusicService:
    def __init__(self, developer_token: str, user_token: Optional[str] = None):
        self.developer_token = developer_token
        self.user_token = user_token
        self.base_url = "https://api.music.apple.com/v1"
        self.client = self._create_client()

    def _create_client(self) -> httpx.AsyncClient:
        """Create httpx client with current tokens"""
        headers = {
            "Authorization": f"Bearer {self.developer_token}",
            "Content-Type": "application/json"
        }
        
        if self.user_token:
            headers["Music-User-Token"] = self.user_token

        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=15.0
        )

    def set_tokens(self, developer_token: str, user_token: Optional[str] = None):
        """Update tokens and recreate client"""
        self.developer_token = developer_token
        self.user_token = user_token
        self.client = self._create_client()
        print("✅ AppleMusicService tokens updated")

    def set_user_token(self, user_token: str):
        """Set user token only"""
        self.user_token = user_token
        self.client = self._create_client()
        print("✅ AppleMusicService user token updated")

    async def get_user_library(self, limit: int = 25, offset: int = 0) -> Dict[str, Any]:
        """Get user's music library"""
        print(f"📡 AppleMusicService.get_user_library: requesting limit={limit} offset={offset}")
        try:
            response = await self.client.get(
                "/me/library/songs",
                params={"limit": limit, "offset": offset}
            )
            response.raise_for_status()
            data = response.json()
            
            count = len(data.get("data", [])) if isinstance(data.get("data"), list) else 0
            print(f"✅ AppleMusicService.get_user_library: received {count} items (limit={limit} offset={offset})")
            return data
        except Exception as e:
            print(f"❌ AppleMusicService.get_user_library error: {str(e)}")
            raise

    async def search_songs(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for songs in the catalog"""
        print(f"📡 AppleMusicService.search_songs: query=\"{query}\" limit={limit}")
        try:
            response = await self.client.get(
                "/catalog/us/search",
                params={
                    "term": query,
                    "types": "songs",
                    "limit": limit
                }
            )
            response.raise_for_status()
            data = response.json()
            
            found = len(data.get("results", {}).get("songs", {}).get("data", []))
            print(f"✅ AppleMusicService.search_songs: found {found} songs for \"{query}\"")
            return data
        except Exception as e:
            print(f"❌ AppleMusicService.search_songs error: {str(e)}")
            raise

    async def get_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """Get a playlist by ID"""
        print(f"📡 AppleMusicService.get_playlist: fetching playlist {playlist_id}")
        try:
            response = await self.client.get(f"/catalog/us/playlists/{playlist_id}")
            response.raise_for_status()
            data = response.json()
            
            print(f"✅ AppleMusicService.get_playlist: playlist {playlist_id} fetched")
            return data
        except Exception as e:
            print(f"❌ AppleMusicService.get_playlist error: {str(e)}")
            raise

    async def add_song_to_library(self, song_id: str) -> Dict[str, Any]:
        """Add a song to user's library"""
        print(f"📡 AppleMusicService.add_song_to_library: adding song {song_id}")
        try:
            response = await self.client.post(
                "/me/library",
                json={"data": [{"id": song_id, "type": "songs"}]}
            )
            response.raise_for_status()
            data = response.json() if response.content else {}
            
            print(f"✅ AppleMusicService.add_song_to_library: added song {song_id}")
            return data
        except Exception as e:
            print(f"❌ AppleMusicService.add_song_to_library error: {str(e)}")
            raise

    async def remove_song_from_library(self, song_id: str) -> Dict[str, Any]:
        """Remove a song from user's library"""
        print(f"📡 AppleMusicService.remove_song_from_library: removing song {song_id}")
        try:
            await self.client.delete(f"/me/library/songs/{song_id}")
            
            print(f"✅ AppleMusicService.remove_song_from_library: removed song {song_id}")
            return {"success": True, "songId": song_id}
        except Exception as e:
            print(f"❌ AppleMusicService.remove_song_from_library error: {str(e)}")
            raise

    async def get_artist(self, artist_id: str) -> Dict[str, Any]:
        """Get an artist by ID"""
        print(f"📡 AppleMusicService.get_artist: fetching artist {artist_id}")
        try:
            response = await self.client.get(f"/catalog/us/artists/{artist_id}")
            response.raise_for_status()
            data = response.json()
            
            print(f"✅ AppleMusicService.get_artist: artist {artist_id} fetched")
            return data
        except Exception as e:
            print(f"❌ AppleMusicService.get_artist error: {str(e)}")
            raise

    async def get_recent_played_tracks(self, limit: int = 30) -> Dict[str, Any]:
        """Get user's recently played tracks"""
        print(f"📡 AppleMusicService.get_recent_played_tracks: fetching recent tracks (limit={limit})")
        try:
            response = await self.client.get(
                "/me/recent/played/tracks",
                params={"limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            
            count = len(data.get("data", [])) if isinstance(data.get("data"), list) else 0
            print(f"✅ AppleMusicService.get_recent_played_tracks: received {count} tracks")
            return data
        except Exception as e:
            print(f"❌ AppleMusicService.get_recent_played_tracks error: {str(e)}")
            raise

    async def get_catalog_songs(self, ids: str, storefront: str = "in") -> Dict[str, Any]:
        """
        Get catalog songs by IDs (to fetch full metadata including genres)
        
        Args:
            ids: Comma-separated song IDs
            storefront: Storefront code (e.g., 'in' for India, 'us' for US)
        """
        print(f"📡 AppleMusicService.get_catalog_songs: fetching catalog songs (storefront={storefront})")
        try:
            response = await self.client.get(
                f"/catalog/{storefront}/songs",
                params={"ids": ids}
            )
            response.raise_for_status()
            data = response.json()
            
            count = len(data.get("data", [])) if isinstance(data.get("data"), list) else 0
            print(f"✅ AppleMusicService.get_catalog_songs: received {count} songs from catalog")
            return data
        except Exception as e:
            print(f"❌ AppleMusicService.get_catalog_songs error: {str(e)}")
            raise

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
