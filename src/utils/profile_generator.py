"""
Profile Generator Utility
Generates user profiles from Apple Music data
"""

from typing import Dict, Any, List, Optional


def generate_user_profile(music_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a user profile from music data"""
    return {
        "id": music_data.get("id"),
        "name": music_data.get("name"),
        "favoriteGenres": extract_genres(music_data.get("playlists")),
        "totalSongsLiked": len(music_data.get("likedSongs", [])),
        "recentActivity": music_data.get("recentActivity", []),
        "preferences": {
            "explicitContent": music_data.get("preferences", {}).get("explicit", False),
            "audioQuality": music_data.get("preferences", {}).get("quality", "standard")
        }
    }


def extract_genres(playlists: Optional[List[Dict[str, Any]]]) -> List[str]:
    """Extract unique genres from playlists"""
    genres = set()
    if playlists and isinstance(playlists, list):
        for playlist in playlists:
            if playlist.get("genre"):
                genres.add(playlist["genre"])
    return list(genres)
