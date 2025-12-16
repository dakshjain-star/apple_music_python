"""
Authentication Service
Handles user authentication and session management for Apple Music
"""

import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from motor.motor_asyncio import AsyncIOMotorClient


class AuthService:
    def __init__(self, mongo_uri: str, token_generator):
        self.mongo_uri = mongo_uri
        self.token_generator = token_generator
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.users_collection = None

    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client.get_default_database()
            self.users_collection = self.db.users
            
            # Create index on userId
            await self.users_collection.create_index(
                "appleMusicUserId",
                unique=True,
                sparse=True
            )
            
            print("✅ AuthService connected to MongoDB")
            return True
        except Exception as e:
            print(f"❌ AuthService MongoDB connection error: {str(e)}")
            raise

    def get_developer_token(self) -> str:
        """Get the developer token for MusicKit JS initialization"""
        return self.token_generator.get_token()

    async def authenticate_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register or update a user after Apple Music authentication
        
        Args:
            user_data: User data from MusicKit JS containing:
                - userToken: The Apple Music user token
                - appleMusicUserId: User identifier
                - displayName: Display name
                - storefront: Storefront code
        """
        try:
            user_token = user_data.get("userToken")
            apple_music_user_id = user_data.get("appleMusicUserId")
            display_name = user_data.get("displayName")
            storefront = user_data.get("storefront", "us")
            
            if not user_token:
                raise ValueError("User token is required")

            # Generate a unique user ID if not provided
            identifier = apple_music_user_id or f"user_{int(datetime.now().timestamp())}_{hash(user_token) % 1000000}"

            # Upsert user document
            result = await self.users_collection.update_one(
                {"appleMusicUserId": identifier},
                {
                    "$set": {
                        "userToken": user_token,
                        "displayName": display_name or f"User_{identifier[-6:]}",
                        "storefront": storefront,
                        "lastLogin": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "appleMusicUserId": identifier,
                        "createdAt": datetime.utcnow()
                    }
                },
                upsert=True
            )

            print(f"✅ User authenticated: {identifier}")

            # Create user-specific collection name (sanitized)
            collection_name = self.get_user_collection_name(identifier)

            return {
                "success": True,
                "user_id": identifier,
                "collection_name": collection_name,
                "is_new_user": result.upserted_id is not None
            }
        except Exception as e:
            print(f"❌ User authentication error: {str(e)}")
            raise

    async def get_user(self, apple_music_user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by their Apple Music User ID"""
        try:
            user = await self.users_collection.find_one({"appleMusicUserId": apple_music_user_id})
            return user
        except Exception as e:
            print(f"❌ Error fetching user: {str(e)}")
            raise

    async def get_user_token(self, apple_music_user_id: str) -> Optional[str]:
        """Get user's stored token"""
        try:
            user = await self.get_user(apple_music_user_id)
            return user.get("userToken") if user else None
        except Exception as e:
            print(f"❌ Error fetching user token: {str(e)}")
            raise

    def get_user_collection_name(self, user_id: str) -> str:
        """Generate a sanitized collection name for a user"""
        # Sanitize the user ID to create a valid MongoDB collection name
        # Replace special characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9]', '_', user_id)
        # If the user_id already starts with "user_", don't add it again
        if sanitized.startswith("user_"):
            return sanitized
        return f"user_{sanitized}"

    async def list_users(self) -> List[Dict[str, Any]]:
        """List all registered users"""
        try:
            cursor = self.users_collection.find(
                {},
                {
                    "appleMusicUserId": 1,
                    "displayName": 1,
                    "storefront": 1,
                    "userToken": 1,
                    "lastLogin": 1,
                    "createdAt": 1
                }
            )
            users = await cursor.to_list(length=None)
            return users
        except Exception as e:
            print(f"❌ Error listing users: {str(e)}")
            raise

    async def update_user_name(self, apple_music_user_id: str, display_name: str) -> bool:
        """Update user's display name"""
        try:
            result = await self.users_collection.update_one(
                {"appleMusicUserId": apple_music_user_id},
                {"$set": {"displayName": display_name}}
            )
            
            if result.matched_count > 0:
                print(f"✅ Updated user name: {apple_music_user_id} -> {display_name}")
                return True
            else:
                print(f"⚠️ User not found: {apple_music_user_id}")
                return False
        except Exception as e:
            print(f"❌ Error updating user name: {str(e)}")
            raise

    async def delete_user(self, apple_music_user_id: str) -> Dict[str, Any]:
        """Delete a user and their collection"""
        try:
            collection_name = self.get_user_collection_name(apple_music_user_id)
            
            # Drop user's personal collection
            try:
                await self.db[collection_name].drop()
                print(f"🗑️ Dropped collection: {collection_name}")
            except Exception:
                # Collection might not exist
                pass

            # Remove user from users collection
            await self.users_collection.delete_one({"appleMusicUserId": apple_music_user_id})
            
            print(f"✅ Deleted user: {apple_music_user_id}")
            return {"success": True, "userId": apple_music_user_id}
        except Exception as e:
            print(f"❌ Error deleting user: {str(e)}")
            raise

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            print("🔌 AuthService disconnected from MongoDB")
