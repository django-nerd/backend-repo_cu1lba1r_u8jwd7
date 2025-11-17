import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sessions (required for OAuth state)
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, https_only=False)

# OAuth setup
config = Config(environ=os.environ)
oauth = OAuth(config)

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID") or "",
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET") or "",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/auth/login")
async def auth_login(request: Request):
    try:
        redirect_uri = f"{BACKEND_URL}/auth/callback"
        return await oauth.google.authorize_redirect(request, redirect_uri)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/callback")
async def auth_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user = token.get("userinfo")
        if not user:
            # Some providers put userinfo under "id_token" claims
            user = token.get("id_token")
        # On success, redirect back to frontend with basic user info as URL hash (not query)
        # to avoid sending it to server logs via proxies.
        redirect = RedirectResponse(
            url=f"{FRONTEND_URL}/#logged_in=1&name={user.get('name','')}&email={user.get('email','')}"
        )
        return redirect
    except OAuthError as e:
        return RedirectResponse(url=f"{FRONTEND_URL}/#error={str(e)}")
    except Exception as e:
        return RedirectResponse(url=f"{FRONTEND_URL}/#error={str(e)}")

@app.get("/auth/me")
async def auth_me(request: Request):
    # This demo implementation doesn't persist sessions, just a placeholder endpoint
    return JSONResponse({"status": "no-session", "message": "Use the login flow to get user info in frontend hash."})

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
