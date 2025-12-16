"""
Sync Controller
Handles synchronization between Apple Music and MongoDB
Generates user listening profile text (not per-song embeddings)
"""

from typing import Dict, Any, List, Tuple

from ..services.apple_music import AppleMusicService
from ..services.vector_store import VectorStoreService
from ..services.embedding_service import get_embedding_service


class SyncController:
    def __init__(self, apple_music_service: AppleMusicService, vector_store_service: VectorStoreService):
        self.music_service = apple_music_service
        self.vector_store = vector_store_service
        self.embedding_service = get_embedding_service()

    async def sync_user_profile(self, user_id: str, storefront: str = "in") -> Dict[str, Any]:
        """
        Synchronize user's Apple Music listening profile with MongoDB
        Fetches recent played tracks, extracts genres from catalog, generates profile text
        """
        try:
            print(f"🔄 SyncController.sync_user_profile: Starting profile sync for user {user_id}")

            # Step 1: Fetch recent played tracks
            print("📥 Step 1: Fetching recent played tracks...")
            recent_tracks = await self.music_service.get_recent_played_tracks(30)
            songs = recent_tracks.get("data", [])
            
            if not songs:
                print("⚠️ No recent tracks found")
                return {"success": False, "message": "No recent tracks found"}
            print(f"✅ Fetched {len(songs)} recent tracks")

            # Step 2: Extract song IDs for catalog lookup
            print("📥 Step 2: Extracting song IDs for catalog lookup...")
            ids = ",".join([song.get("id") for song in songs if song.get("id")])
            print(f"✅ Extracted {len(songs)} song IDs")

            # Step 3: Fetch catalog data (to get full metadata including genres)
            print(f"📥 Step 3: Fetching catalog data (storefront={storefront})...")
            catalog_response = await self.music_service.get_catalog_songs(ids, storefront)
            catalog_data = catalog_response.get("data", [])
            print(f"✅ Fetched catalog data for {len(catalog_data)} songs")

            # Step 4: Generate profile text from catalog data
            print("📝 Step 4: Generating profile text...")
            profile_text, top_genres = self._generate_profile_text(catalog_data)
            print(f"✅ Generated profile text ({len(profile_text)} chars)")
            print(f"🎵 Top Genres: {', '.join(top_genres)}")

            # Step 5: Generate embeddings from profile text
            print("🔢 Step 5: Generating embeddings using sentence-transformers...")
            embedding = self.embedding_service.generate_embedding(profile_text)
            print(f"✅ Generated {len(embedding)}-dimensional embedding")

            # Step 6: Store profile in MongoDB
            print("💾 Step 6: Storing profile in MongoDB...")
            await self.vector_store.store_user_profile(user_id, profile_text, embedding)
            
            print(f"✅ SyncController.sync_user_profile: Finished for user {user_id}")
            return {
                "success": True,
                "user_id": user_id,
                "profile_text": profile_text,
                "top_genres": top_genres,
                "songs_processed": len(catalog_data),
                "embedding_dim": len(embedding)
            }
        except Exception as e:
            print(f"❌ SyncController.sync_user_profile error: {str(e)}")
            raise

    def _generate_profile_text(self, catalog_data: List[Dict]) -> Tuple[str, List[str]]:
        """
        Generate profile text string from catalog data
        Format: "User Listening Profile: Song: X, Artist: Y, Genre: Z. ... Top Genres: A, B, C."
        """
        profile_text = "User Listening Profile: "
        genres: Dict[str, int] = {}

        for item in catalog_data:
            attrs = item.get("attributes", {})
            genre_names = attrs.get("genreNames", [])
            genre = genre_names[0] if genre_names else "Unknown"
            
            profile_text += f"Song: {attrs.get('name', 'Unknown')}, Artist: {attrs.get('artistName', 'Unknown')}, Genre: {genre}. "
            
            if genre and genre != "Unknown":
                genres[genre] = genres.get(genre, 0) + 1

        # Add top genres to summary
        top_genres = sorted(genres.keys(), key=lambda x: genres[x], reverse=True)[:3]
        
        profile_text += f"Top Genres: {', '.join(top_genres)}."

        return profile_text, top_genres

    def _generate_profile_embedding(self, profile_text: str) -> List[float]:
        """
        Generate embedding vector from profile text
        Creates a 128-dimensional vector from text features (fallback method)
        """
        try:
            import math
            import re
            
            features: List[float] = []

            # Feature 1: Text length (normalized)
            features.append(min(len(profile_text) / 1000, 1))

            # Feature 2-4: Hash of genre mentions
            genre_matches = re.findall(r'Genre: ([^.]+)', profile_text)
            features.append(len(genre_matches) / 50)

            # Feature 5-7: Hash of "Song:" occurrences
            song_matches = re.findall(r'Song:', profile_text)
            features.append(len(song_matches) / 50)

            # Feature 8-10: Hash of top genres section
            top_genre_match = re.search(r'Top Genres: (.+)', profile_text)
            features.append(1.0 if top_genre_match else 0.0)

            # Extract individual words for TF-IDF-like features
            words = re.findall(r'\b\w+\b', profile_text.lower())
            word_freq: Dict[str, int] = {}
            for word in words:
                if len(word) > 3:  # Skip short words
                    word_freq[word] = word_freq.get(word, 0) + 1

            # Top words as features
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]

            for word, freq in top_words:
                features.append((freq / len(words)) * 10)

            # Fill remaining dimensions with character-based hashing
            char_codes = [ord(c) for c in profile_text]
            while len(features) < 128:
                idx = (len(features) - 1) % len(char_codes) if char_codes else 0
                value = (char_codes[idx] / 256) * 0.1 if char_codes else 0.1
                features.append(value)

            # Normalize to 128 dimensions
            embedding = features[:128]

            # Normalize the vector (unit normalization)
            magnitude = math.sqrt(sum(val * val for val in embedding))
            if magnitude > 0:
                embedding = [val / magnitude for val in embedding]

            return embedding
        except Exception as e:
            print(f"Error generating profile embedding: {str(e)}")
            # Return random fallback
            import random
            return [random.random() * 0.1 for _ in range(128)]

    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile from MongoDB"""
        try:
            profile = await self.vector_store.get_vector(user_id, f"profile_{user_id}")
            return profile
        except Exception as e:
            print(f"Error getting user profile: {str(e)}")
            raise

    async def get_sync_status(self, user_id: str) -> Dict[str, Any]:
        """Get synchronization status"""
        try:
            profile = await self.vector_store.get_vector(user_id, f"profile_{user_id}")
            
            return {
                "is_synced": profile is not None,
                "user_id": profile.get("_id", user_id) if profile else user_id,
                "last_update": profile.get("timestamp") if profile else None,
                "has_profile_text": bool(profile.get("text")) if profile else False
            }
        except Exception as e:
            print(f"Error getting sync status: {str(e)}")
            raise
