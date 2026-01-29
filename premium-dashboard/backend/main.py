from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from typing import List

from .auth import (
    create_access_token, 
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    verify_password,
    get_user,
    pwd_context
)
from .schemas import Token, User, WishlistUpdate
from .data_service import get_tracks_data, get_geojson_data, load_wishlist, update_wishlist

app = FastAPI(title="MP Intelligence API")

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to dashboard domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes with /api prefix
@app.post("/api/auth/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/api/tracks")
async def read_tracks(current_user: User = Depends(get_current_user)):
    return get_tracks_data()

@app.get("/api/tracks/shapes")
async def read_shapes(current_user: User = Depends(get_current_user)):
    from fastapi.responses import Response
    content = get_geojson_data(as_string=True)
    return Response(content=content, media_type="application/json")

@app.get("/api/wishlist")
async def get_wishlist(current_user: User = Depends(get_current_user)):
    return load_wishlist(current_user.username)

@app.post("/api/wishlist")
async def post_wishlist(update: WishlistUpdate, current_user: User = Depends(get_current_user)):
    return update_wishlist(current_user.username, update.track_id, update.action)

@app.get("/api/health")
async def root():
    return {"message": "MP Intelligence API is LIVE", "status": "Ready"}

# Serve Frontend Static Files
from fastapi.staticfiles import StaticFiles
import os

# Important: Mount static files AFTER API routes to avoid conflicts
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Cloud Run assigns a PORT environment variable
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)
