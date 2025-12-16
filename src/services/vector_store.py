"""
Vector Store Service
Manages vector embeddings in MongoDB with similarity search
Supports per-user collections
"""

import re
import math
from datetime import datetime
from typing import Optional, Dict, Any, List

from motor.motor_asyncio import AsyncIOMotorClient


class VectorStoreService:
    def __init__(self, mongo_uri: str):
        self.mongo_uri = mongo_uri
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.collections: Dict[str, Any] = {}  # Cache for user collections

    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client.get_default_database()
            
            print("✅ Connected to MongoDB")
            return True
        except Exception as e:
            print(f"Error connecting to MongoDB: {str(e)}")
            raise

    async def get_user_collection(self, user_id: str):
        """Get or create a collection for a specific user"""
        collection_name = self.get_user_collection_name(user_id)
        
        print(f"📦 get_user_collection: user_id='{user_id}' → collection='{collection_name}'")
        
        if collection_name in self.collections:
            return self.collections[collection_name]

        collection = self.db[collection_name]
        await self._ensure_indexes(collection, collection_name)
        self.collections[collection_name] = collection
        
        print(f"📦 Using collection: {collection_name}")
        return collection

    def get_user_collection_name(self, user_id: str) -> str:
        """Generate a sanitized collection name for a user"""
        sanitized = re.sub(r'[^a-zA-Z0-9]', '_', user_id)
        # If the user_id already starts with "user_", don't add it again
        if sanitized.startswith("user_"):
            return sanitized
        return f"user_{sanitized}"

    async def _ensure_indexes(self, collection, collection_name: str):
        """Ensure necessary indexes are created"""
        try:
            # Create index for metadata fields
            await collection.create_index([("metadata.type", 1), ("metadata.id", 1)])
            
            # Create index for timestamps
            await collection.create_index("timestamp")
            
            print(f"✅ Indexes created for {collection_name}")
        except Exception as e:
            # Index might already exist, which is fine
            if "already exists" not in str(e):
                print(f"Index creation warning: {str(e)}")

    async def store_vector(self, user_id: str, doc_id: str, embedding: List[float], metadata: Dict = None) -> Dict[str, Any]:
        """Store a vector embedding for a song/user profile"""
        try:
            collection = await self.get_user_collection(user_id)
            vector_doc = {
                "_id": doc_id,
                "embedding": embedding,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow()
            }

            result = await collection.update_one(
                {"_id": doc_id},
                {"$set": vector_doc},
                upsert=True
            )

            return {
                "success": True,
                "id": doc_id,
                "upserted": result.upserted_id is not None
            }
        except Exception as e:
            print(f"Error storing vector: {str(e)}")
            raise

    async def store_user_profile(self, user_id: str, profile_text: str, embedding: List[float] = None) -> Dict[str, Any]:
        """
        Store user profile with text field (for embedding generation by external service)
        Document format matches MongoDB Atlas Vector Store expectations
        """
        try:
            collection = await self.get_user_collection(user_id)
            collection_name = self.get_user_collection_name(user_id)
            
            profile_doc = {
                "_id": f"profile_{user_id}",
                "text": profile_text,  # This is the field used for embedding generation
                "embedding": embedding or [],  # Empty array if embedding is generated externally
                "metadata": {
                    "source": "blob",
                    "blobType": "application/json",
                    "loc": {
                        "lines": {
                            "from": 1,
                            "to": 1
                        }
                    }
                },
                "pageContent": profile_text,  # Alternative field name used by some vector stores
                "timestamp": datetime.utcnow()
            }

            result = await collection.update_one(
                {"_id": profile_doc["_id"]},
                {"$set": profile_doc},
                upsert=True
            )

            print(f"✅ Stored profile for user {user_id} in collection '{collection_name}'")
            return {
                "success": True,
                "user_id": user_id,
                "collection_name": collection_name,
                "upserted": result.upserted_id is not None
            }
        except Exception as e:
            print(f"Error storing user profile: {str(e)}")
            raise

    async def get_vector(self, user_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a vector by ID"""
        try:
            collection = await self.get_user_collection(user_id)
            result = await collection.find_one({"_id": doc_id})
            return result
        except Exception as e:
            print(f"Error retrieving vector: {str(e)}")
            raise

    def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if not vec_a or not vec_b:
            return 0.0
        if len(vec_a) != len(vec_b):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        magnitude_a = math.sqrt(sum(a * a for a in vec_a))
        magnitude_b = math.sqrt(sum(b * b for b in vec_b))

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        return dot_product / (magnitude_a * magnitude_b)

    async def find_similar(self, user_id: str, query_vector: List[float], top_k: int = 10, metadata_filter: Dict = None) -> List[Dict]:
        """Find similar vectors using cosine similarity (fallback method)"""
        try:
            collection = await self.get_user_collection(user_id)
            query = self._build_metadata_filter(metadata_filter or {})
            cursor = collection.find(query)
            docs = await cursor.to_list(length=None)
            
            results = []
            for doc in docs:
                embedding = doc.get("embedding", [])
                if embedding:
                    similarity = self.cosine_similarity(query_vector, embedding)
                    results.append({
                        "id": doc["_id"],
                        "similarity": similarity,
                        "metadata": doc.get("metadata", {}),
                        "timestamp": doc.get("timestamp")
                    })

            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:top_k]
        except Exception as e:
            print(f"Error finding similar vectors: {str(e)}")
            raise

    def _build_metadata_filter(self, metadata_filter: Dict) -> Dict:
        """Build metadata filter for queries"""
        if not metadata_filter:
            return {}
        return {f"metadata.{key}": value for key, value in metadata_filter.items()}

    async def delete_vector(self, user_id: str, doc_id: str) -> Dict[str, Any]:
        """Delete a vector by ID"""
        try:
            collection = await self.get_user_collection(user_id)
            result = await collection.delete_one({"_id": doc_id})
            return {
                "success": result.deleted_count > 0,
                "id": doc_id,
                "deleted_count": result.deleted_count
            }
        except Exception as e:
            print(f"Error deleting vector: {str(e)}")
            raise

    async def drop_user_collection(self, user_id: str) -> Dict[str, Any]:
        """Drop a user's collection entirely"""
        try:
            collection_name = self.get_user_collection_name(user_id)
            await self.db[collection_name].drop()
            if collection_name in self.collections:
                del self.collections[collection_name]
            print(f"🗑️ Dropped collection: {collection_name}")
            return {"success": True, "collection_name": collection_name}
        except Exception as e:
            if "ns not found" in str(e):
                return {"success": True, "message": "Collection did not exist"}
            print(f"Error dropping collection: {str(e)}")
            raise

    async def get_all_user_collections(self) -> List[str]:
        """Get all user collections in the database"""
        try:
            collections = await self.db.list_collection_names()
            return [c for c in collections if c.startswith("user_")]
        except Exception as e:
            print(f"Error listing user collections: {str(e)}")
            raise

    async def get_user_profile_embedding(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile embedding"""
        try:
            profile_id = f"profile_{user_id}"
            print(f"🔍 Looking for profile: user_id='{user_id}', profile_id='{profile_id}'")
            
            profile = await self.get_vector(user_id, profile_id)
            
            if not profile:
                print(f"❌ Profile document not found for {user_id}")
                return None
                
            if not profile.get("embedding"):
                print(f"❌ Profile found but no embedding field for {user_id}")
                return None
                
            if len(profile.get("embedding", [])) == 0:
                print(f"❌ Profile found but embedding is empty for {user_id}")
                return None
            
            print(f"✅ Found profile with {len(profile['embedding'])}-dim embedding for {user_id}")
            return {
                "user_id": user_id,
                "embedding": profile["embedding"],
                "text": profile.get("text") or profile.get("pageContent"),
                "timestamp": profile.get("timestamp")
            }
        except Exception as e:
            print(f"❌ Error getting profile embedding for {user_id}: {str(e)}")
            return None

    async def find_similar_users(self, current_user_id: str) -> Dict[str, Any]:
        """Find similar users by comparing profile embeddings"""
        try:
            print(f"\n🔍 Finding similar users for: {current_user_id}")
            
            # Get current user's profile embedding
            current_profile = await self.get_user_profile_embedding(current_user_id)
            if not current_profile:
                print(f"⚠️  No profile embedding found for user: {current_user_id}")
                return {"success": False, "error": "Current user has no profile embedding"}

            print(f"📊 Current user embedding dimensions: {len(current_profile['embedding'])}")

            # Get all user collections
            user_collections = await self.get_all_user_collections()
            print(f"📦 Found {len(user_collections)} user collection(s)")

            similarities = []

            # Compare with all other users
            for collection_name in user_collections:
                # Extract the actual user_id - the collection name is "user_{sanitized_id}"
                # But the actual user_id might be just the sanitized part OR "user_..." format
                # We need to check both formats
                other_user_id = collection_name.replace("user_", "", 1)
                
                # Skip current user (check both with and without user_ prefix)
                current_id_sanitized = current_user_id.replace("user_", "")
                if other_user_id == current_id_sanitized or other_user_id == current_user_id:
                    print(f"⏭️  Skipping current user: {other_user_id}")
                    continue

                # Try to get profile with the extracted user_id
                other_profile = await self.get_user_profile_embedding(other_user_id)
                if not other_profile:
                    print(f"⚠️  Skipping {other_user_id}: No profile embedding")
                    continue

                # Calculate cosine similarity
                similarity = self.cosine_similarity(current_profile["embedding"], other_profile["embedding"])
                similarity_percent = round(similarity * 100, 2)

                print(f"\n👤 Comparing with user: {other_user_id}")
                print(f"   📊 Similarity Score: {similarity_percent}%")

                # Parse profile text to extract details
                profile_details = self._parse_profile_text(other_profile.get("text", ""))

                similarities.append({
                    "userId": other_user_id,
                    "similarity": similarity,
                    "similarityPercent": similarity_percent,
                    "profileText": other_profile.get("text"),
                    **profile_details,
                    "timestamp": other_profile.get("timestamp")
                })

            # Sort by similarity (highest first)
            similarities.sort(key=lambda x: x["similarity"], reverse=True)

            print(f"\n✅ Found {len(similarities)} similar user(s)")
            
            # Log detailed similarity breakdown
            if similarities:
                print("\n📈 ═══════════════════════════════════════════════════════════")
                print("   USER SIMILARITY REPORT")
                print("═══════════════════════════════════════════════════════════════")
                
                for index, user in enumerate(similarities):
                    print(f"\n   {index + 1}. User: {user['userId']}")
                    print(f"      🎯 Similarity: {user['similarityPercent']}%")
                    if user.get("genres"):
                        print(f"      🎸 Genres: {', '.join(user['genres'])}")
                    if user.get("artists"):
                        print(f"      🎤 Artists: {', '.join(user['artists'][:5])}")
                    if user.get("songs"):
                        print(f"      🎵 Songs: {', '.join(user['songs'][:5])}")
                
                print("\n═══════════════════════════════════════════════════════════════\n")

            return {
                "success": True,
                "current_user": current_user_id,
                "similar_users": similarities,
                "total_users_compared": len(similarities)
            }
        except Exception as e:
            print(f"Error finding similar users: {str(e)}")
            raise

    def _parse_profile_text(self, profile_text: str) -> Dict[str, List[str]]:
        """Parse profile text to extract structured data"""
        result = {
            "genres": [],
            "artists": [],
            "songs": [],
            "albums": []
        }

        if not profile_text:
            return result

        try:
            # Extract genres - look for "Genre:" patterns
            import re
            genre_matches = re.findall(r'Genre:\s*([^.]+)', profile_text, re.IGNORECASE)
            for match in genre_matches:
                genre = match.strip()
                if genre and genre not in result["genres"]:
                    result["genres"].append(genre)

            # Extract artists - look for "Artist:" patterns
            artist_matches = re.findall(r'Artist:\s*([^,]+)', profile_text, re.IGNORECASE)
            for match in artist_matches:
                artist = match.strip()
                if artist and artist not in result["artists"]:
                    result["artists"].append(artist)

            # Extract songs - look for "Song:" patterns
            song_matches = re.findall(r'Song:\s*([^,]+)', profile_text, re.IGNORECASE)
            for match in song_matches:
                song = match.strip()
                if song and song not in result["songs"]:
                    result["songs"].append(song)

            # Extract albums - look for "Album:" patterns
            album_matches = re.findall(r'Album:\s*([^,]+)', profile_text, re.IGNORECASE)
            for match in album_matches:
                album = match.strip()
                if album and album not in result["albums"]:
                    result["albums"].append(album)
        except Exception as e:
            print(f"Error parsing profile text: {str(e)}")

        return result

    async def find_common_interests(self, user_id1: str, user_id2: str) -> Dict[str, Any]:
        """Find common interests between two users"""
        try:
            print(f"\n🔍 Finding common interests between {user_id1} and {user_id2}")

            profile1 = await self.get_user_profile_embedding(user_id1)
            profile2 = await self.get_user_profile_embedding(user_id2)

            if not profile1 or not profile2:
                return {"success": False, "error": "One or both users have no profile"}

            details1 = self._parse_profile_text(profile1.get("text", ""))
            details2 = self._parse_profile_text(profile2.get("text", ""))

            # Find common genres
            common_genres = [g for g in details1["genres"] 
                          if any(g2.lower() == g.lower() for g2 in details2["genres"])]

            # Find common artists
            common_artists = [a for a in details1["artists"] 
                           if any(a2.lower() == a.lower() for a2 in details2["artists"])]

            # Find common songs
            common_songs = [s for s in details1["songs"] 
                         if any(s2.lower() == s.lower() for s2 in details2["songs"])]

            # Find common albums
            common_albums = [al for al in details1["albums"] 
                          if any(al2.lower() == al.lower() for al2 in details2["albums"])]

            # Calculate overall similarity
            similarity = self.cosine_similarity(profile1["embedding"], profile2["embedding"])

            result = {
                "success": True,
                "userId1": user_id1,
                "userId2": user_id2,
                "similarity": f"{similarity * 100:.2f}",
                "commonInterests": {
                    "genres": common_genres,
                    "artists": common_artists,
                    "songs": common_songs,
                    "albums": common_albums
                },
                "user1Details": details1,
                "user2Details": details2
            }

            print(f"\n📊 Common Interests Report:")
            print(f"   🎯 Similarity: {result['similarity']}%")
            print(f"   🎸 Common Genres: {', '.join(common_genres) if common_genres else 'None'}")
            print(f"   🎤 Common Artists: {', '.join(common_artists) if common_artists else 'None'}")
            print(f"   🎵 Common Songs: {', '.join(common_songs) if common_songs else 'None'}")
            print(f"   💿 Common Albums: {', '.join(common_albums) if common_albums else 'None'}")

            return result
        except Exception as e:
            print(f"Error finding common interests: {str(e)}")
            raise

    async def disconnect(self):
        """Disconnect from MongoDB"""
        try:
            if self.client:
                self.client.close()
                self.collections.clear()
                print("✅ Disconnected from MongoDB")
        except Exception as e:
            print(f"Error disconnecting from MongoDB: {str(e)}")
            raise
