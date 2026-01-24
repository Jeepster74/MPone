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

@app.post("/auth/login", response_model=Token)
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

@app.get("/tracks")
async def read_tracks(current_user: User = Depends(get_current_user)):
    return get_tracks_data()

@app.get("/tracks/shapes")
async def read_shapes(current_user: User = Depends(get_current_user)):
    return get_geojson_data()

@app.get("/wishlist")
async def get_wishlist(current_user: User = Depends(get_current_user)):
    return load_wishlist(current_user.username)

@app.post("/wishlist")
async def post_wishlist(update: WishlistUpdate, current_user: User = Depends(get_current_user)):
    return update_wishlist(current_user.username, update.track_id, update.action)

@app.get("/")
async def root():
    return {"message": "MP Intelligence API is LIVE", "status": "Ready"}
