# Apple Music Python (FastAPI)

Apple Music integration with Python FastAPI backend - a Python port of the Node.js version.

## Features

- Apple Music authentication using MusicKit JS
- User profile synchronization with MongoDB
- Vector embeddings for music taste analysis
- Similar user discovery based on listening profiles

## Prerequisites

- Python 3.9+
- MongoDB instance
- Apple Developer Account with MusicKit access
- Apple Music API credentials (.p8 key file)

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

4. Configure your environment variables in `.env`

## Running the Server

Development mode:
```bash
uvicorn src.main:app --reload --port 3000
```

Production mode:
```bash
uvicorn src.main:app --host 0.0.0.0 --port 3000
```

## Project Structure

```
python/
├── src/
│   ├── main.py              # FastAPI application entry point
│   ├── controllers/
│   │   └── sync_controller.py
│   ├── services/
│   │   ├── apple_music.py
│   │   ├── auth_service.py
│   │   ├── embedding_service.py
│   │   ├── token_generator.py
│   │   └── vector_store.py
│   └── utils/
│       └── profile_generator.py
├── public/                   # Static frontend files
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── requirements.txt
└── README.md
```

## API Endpoints

- `GET /api/auth/developer-token` - Get Apple Music developer token
- `POST /api/auth/login` - Authenticate user with Apple Music
- `POST /api/sync/{userId}` - Sync user's listening profile
- `GET /api/users/{userId}/profile` - Get user's music profile
- `GET /api/users` - List all registered users
- `GET /api/users/{userId}/similar` - Find similar users
- `GET /api/users/{userId}/compare/{otherUserId}` - Compare two users

## License

MIT
