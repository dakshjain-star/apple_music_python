"""
Main Application Entry Point
FastAPI server with Apple Music authentication and profile sync
"""

import os
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .services.token_generator import TokenGenerator
from .services.auth_service import AuthService
from .services.apple_music import AppleMusicService
from .services.vector_store import VectorStoreService
from .controllers.sync_controller import SyncController

# Load environment variables
load_dotenv()

# Initialize services (will be set during startup)
token_generator: Optional[TokenGenerator] = None
auth_service: Optional[AuthService] = None
vector_store_service: Optional[VectorStoreService] = None

# User sessions (in-memory, use Redis in production)
user_sessions: Dict[str, dict] = {}


# Pydantic models for request/response
class LoginRequest(BaseModel):
    userToken: str
    storefront: Optional[str] = "us"


class SyncRequest(BaseModel):
    storefront: Optional[str] = "us"


class UpdateNameRequest(BaseModel):
    displayName: str


async def initialize_data_fetching():
    """Initialize data fetching for all users on server startup"""
    try:
        print("\n📊 Initializing data fetching for all users...")
        
        users = await auth_service.list_users()
        
        if not users or len(users) == 0:
            print("⚠️  No users found in database. Skipping initial sync.")
            return
        
        print(f"🔄 Found {len(users)} user(s). Starting sync process...")
        
        for user in users:
            try:
                user_id = user.get("appleMusicUserId")
                print(f"\n📌 Syncing user: {user_id}")
                
                if not user.get("userToken"):
                    print(f"⚠️  Skipping user {user_id}: No valid userToken found")
                    continue
                
                developer_token = token_generator.get_token()
                apple_music_service = AppleMusicService(developer_token, user.get("userToken"))
                sync_controller = SyncController(apple_music_service, vector_store_service)
                
                result = await sync_controller.sync_user_profile(user_id, user.get("storefront", "us"))
                
                print(f"✅ Successfully synced user {user_id}")
                print(f"   - Songs processed: {result.get('songs_processed')}")
                print(f"   - Top genres: {', '.join(result.get('top_genres', []))}")
            except Exception as e:
                print(f"❌ Failed to sync user {user.get('appleMusicUserId')}: {str(e)}")
        
        print("\n✅ Data fetching initialization complete!")
    except Exception as e:
        print(f"❌ Error during data fetching initialization: {str(e)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown"""
    global token_generator, auth_service, vector_store_service
    
    print("🎵 Apple Music Python FastAPI Service Starting...")
    
    # Initialize services
    token_generator = TokenGenerator(
        team_id=os.getenv("APPLE_MUSIC_TEAM_ID"),
        key_id=os.getenv("APPLE_MUSIC_KEY_ID"),
        auth_key_path=os.getenv("APPLE_MUSIC_AUTH_KEY_PATH")
    )
    
    auth_service = AuthService(
        mongo_uri=os.getenv("MONGODB_URI"),
        token_generator=token_generator
    )
    
    vector_store_service = VectorStoreService(
        mongo_uri=os.getenv("MONGODB_URI")
    )
    
    # Connect to MongoDB
    await auth_service.connect()
    await vector_store_service.connect()
    
    print("✅ Application initialized successfully")
    print(f"📦 Environment: {os.getenv('NODE_ENV', 'development')}")
    
    # Initialize data fetching in background
    asyncio.create_task(initialize_data_fetching())
    
    yield
    
    # Shutdown
    print("\n🛑 Shutting down gracefully...")
    await vector_store_service.disconnect()
    await auth_service.disconnect()


# Create FastAPI app
app = FastAPI(
    title="Apple Music Profile Sync",
    description="Apple Music integration with Python FastAPI",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), "..", "public")
app.mount("/static", StaticFiles(directory=static_path), name="static")


# ========== API Routes ==========

@app.get("/api/auth/developer-token")
async def get_developer_token():
    """Get developer token for MusicKit JS"""
    try:
        developer_token = token_generator.get_token()
        return {"success": True, "developerToken": developer_token}
    except Exception as e:
        print(f"Error getting developer token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate developer token")


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """User login with Apple Music user token"""
    try:
        if not request.userToken:
            raise HTTPException(status_code=400, detail="User token is required")
        
        # Generate a simple user ID
        import base64
        user_id = f"user_{base64.b64encode(request.userToken[:20].encode()).decode()[:12].replace('+', '').replace('/', '').replace('=', '')}"
        
        result = await auth_service.authenticate_user({
            "userToken": request.userToken,
            "appleMusicUserId": user_id,
            "displayName": f"User_{user_id[-6:]}",
            "storefront": request.storefront or "us"
        })
        
        # Store session
        user_sessions[user_id] = {
            "userToken": request.userToken,
            "storefront": request.storefront or "us"
        }
        
        return {
            "success": True,
            "user": {
                "userId": result["user_id"],
                "displayName": f"User_{result['user_id'][-6:]}",
                "storefront": request.storefront or "us",
                "collectionName": result["collection_name"],
                "isNewUser": result["is_new_user"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")


@app.post("/api/sync/{user_id}")
async def sync_user(user_id: str, request: SyncRequest):
    """Sync user profile"""
    try:
        # Get user session
        session = user_sessions.get(user_id)
        if not session:
            # Try to get from database
            user = await auth_service.get_user(user_id)
            if not user:
                raise HTTPException(status_code=401, detail="User not found. Please login again.")
            if not user.get("userToken"):
                raise HTTPException(status_code=401, detail="No valid token found. Please login again.")
            session = {"userToken": user.get("userToken"), "storefront": user.get("storefront")}
        
        # Create Apple Music service with user's token
        developer_token = token_generator.get_token()
        apple_music_service = AppleMusicService(developer_token, session.get("userToken"))
        
        # Create sync controller
        sync_controller = SyncController(apple_music_service, vector_store_service)
        
        # Sync profile
        storefront = request.storefront or session.get("storefront", "us")
        result = await sync_controller.sync_user_profile(user_id, storefront)
        
        return {
            "success": True,
            "userId": result["user_id"],
            "topGenres": result["top_genres"],
            "songsProcessed": result["songs_processed"],
            "collectionName": vector_store_service.get_user_collection_name(user_id)
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"Sync error: {error_msg}")
        # Check for token expiry errors
        if "401" in error_msg or "Unauthorized" in error_msg or "expired" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Token expired or invalid. Please login again to refresh your token.")
        raise HTTPException(status_code=500, detail=f"Sync failed: {error_msg}")


@app.post("/api/users/{user_id}/update-name")
async def update_user_name(user_id: str, request: UpdateNameRequest):
    """Update user's display name"""
    try:
        print(f"\n✏️ API Request: Update name for {user_id} to '{request.displayName}'")
        
        # Update user's display name in database
        result = await auth_service.update_user_name(user_id, request.displayName)
        
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "userId": user_id,
            "displayName": request.displayName
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating user name: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update user name")


@app.get("/api/users/{user_id}/profile")
async def get_user_profile(user_id: str):
    """Get user profile"""
    try:
        profile = await vector_store_service.get_vector(user_id, f"profile_{user_id}")
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        return {
            "success": True,
            "profile": {
                "text": profile.get("text"),
                "timestamp": profile.get("timestamp"),
                "collectionName": vector_store_service.get_user_collection_name(user_id)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get profile")


@app.get("/api/users")
async def list_users():
    """List all users with their basic info"""
    try:
        users = await auth_service.list_users()
        # Format users for response (exclude sensitive token data)
        formatted_users = []
        for user in users:
            formatted_users.append({
                "appleMusicUserId": user.get("appleMusicUserId"),
                "displayName": user.get("displayName", f"User_{user.get('appleMusicUserId', '')[-6:]}"),
                "storefront": user.get("storefront", "us"),
                "lastLogin": user.get("lastLogin").isoformat() if user.get("lastLogin") else None,
                "createdAt": user.get("createdAt").isoformat() if user.get("createdAt") else None,
                "hasToken": bool(user.get("userToken"))
            })
        return {"success": True, "users": formatted_users}
    except Exception as e:
        print(f"Error listing users: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list users")


@app.get("/api/users/{user_id}/details")
async def get_user_details(user_id: str):
    """Get detailed user info including profile data (for existing users view)"""
    try:
        # Get user from database
        user = await auth_service.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get profile if exists
        profile = await vector_store_service.get_vector(user_id, f"profile_{user_id}")
        
        return {
            "success": True,
            "user": {
                "userId": user.get("appleMusicUserId"),
                "displayName": user.get("displayName", f"User_{user_id[-6:]}"),
                "storefront": user.get("storefront", "us"),
                "hasToken": bool(user.get("userToken")),
                "lastLogin": user.get("lastLogin").isoformat() if user.get("lastLogin") else None
            },
            "hasProfile": profile is not None,
            "profile": {
                "timestamp": profile.get("timestamp") if profile else None,
                "hasEmbedding": bool(profile.get("embedding")) if profile else False
            } if profile else None
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting user details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get user details")


@app.get("/api/users/{user_id}/similar")
async def find_similar_users(user_id: str):
    """Find similar users for a given user (Vector Similarity Search)"""
    try:
        print(f"\n🔍 API Request: Find similar users for {user_id}")
        
        result = await vector_store_service.find_similar_users(user_id)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400, 
                detail=result.get("error", "Failed to find similar users")
            )
        
        return {
            "success": True,
            "currentUser": result["current_user"],
            "similarUsers": result["similar_users"],
            "totalUsersCompared": result["total_users_compared"]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error finding similar users: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to find similar users")


@app.get("/api/users/{user_id}/compare/{other_user_id}")
async def compare_users(user_id: str, other_user_id: str):
    """Find common interests between two users"""
    try:
        print(f"\n🔍 API Request: Compare {user_id} with {other_user_id}")
        
        result = await vector_store_service.find_common_interests(user_id, other_user_id)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400, 
                detail=result.get("error", "Failed to compare users")
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error comparing users: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to compare users")


@app.get("/api/users/profiles/all")
async def get_all_profiles():
    """Get all user profiles with embeddings summary"""
    try:
        print("\n📊 API Request: Get all user profiles")
        
        users = await auth_service.list_users()
        profiles = []
        
        for user in users:
            user_id = user.get("appleMusicUserId")
            profile = await vector_store_service.get_vector(user_id, f"profile_{user_id}")
            
            if profile:
                has_embedding = profile.get("embedding") and len(profile.get("embedding", [])) > 0
                profiles.append({
                    "userId": user_id,
                    "displayName": f"User_{user_id[-6:]}",
                    "hasEmbedding": has_embedding,
                    "embeddingDimensions": len(profile.get("embedding", [])) if has_embedding else 0,
                    "timestamp": profile.get("timestamp"),
                    "collectionName": vector_store_service.get_user_collection_name(user_id)
                })
        
        print(f"✅ Found {len(profiles)} user profile(s) with embeddings")
        
        return {
            "success": True,
            "profiles": profiles,
            "totalUsers": len(profiles)
        }
    except Exception as e:
        print(f"Error getting all profiles: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get user profiles")


@app.get("/")
async def serve_index():
    """Serve the main app"""
    return FileResponse(os.path.join(static_path, "index.html"))


# Catch-all for static files
@app.get("/{path:path}")
async def serve_static(path: str):
    """Serve static files"""
    file_path = os.path.join(static_path, path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse(os.path.join(static_path, "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 3000))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)
