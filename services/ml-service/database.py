"""
CineScope ML Service — Database & Data Connector

Connects to MongoDB for user-specific data (ratings, preferences, watchlists).
Movie data is fetched from TMDB API instead of a local MongoDB collection.
"""

import os
from pymongo import MongoClient
from bson import ObjectId
from tmdb_client import (
    fetch_popular_movies, fetch_trending_movies, fetch_genre_list,
    fetch_discover_movies, fetch_movie_details
)

_client = None
_db = None


def get_database():
    """Get or create the MongoDB connection."""
    global _client, _db
    if _db is not None:
        return _db

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/cinescope")
    # Add timeouts to prevent the service from hanging on bad connections
    _client = MongoClient(
        mongo_uri, 
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=30000
    )
    _db = _client.get_default_database(default="test")
    _client.admin.command("ping")
    print("[ml-service] MongoDB connected")
    return _db


def get_all_movies():
    """
    Load a large, diverse pool of movies from TMDB.
    Combines global popular, top rated, and regional hits.
    """
    print("[ml-service] Fetching diverse movie pool from TMDB...")
    
    movies_dict = {}
    
    # 1. Global Popular (High coverage)
    try:
        popular = fetch_popular_movies(pages=15)
        for m in popular:
            movies_dict[m["movie_id"]] = m
    except Exception as e:
        print(f"[ml-service] Popular fetch failed: {e}")
        
    # 2. Trending (Current hits)
    try:
        trending = fetch_trending_movies(limit=80)
        for m in trending:
            movies_dict[m["movie_id"]] = m
    except Exception as e:
        print(f"[ml-service] Trending fetch failed: {e}")

    # 3. Regional Discovery (Specifically targeting user's likely interests)
    # We fetch a few pages of popular movies in common regional languages
    for lang in ["ta", "hi", "te", "ml"]: # Added Malayalam
        try:
            regional = fetch_discover_movies(language=lang, pages=8) # Increased to 8 pages
            for m in regional:
                movies_dict[m["movie_id"]] = m
        except Exception as e:
            print(f"[ml-service] {lang} fetch failed: {e}")

    # 4. User History Movies (CRITICAL: ensure all liked/rated movies are in the model)
    try:
        db = get_database()
        
        # Get all movie IDs from watchlists and ratings
        history_ids = set()
        
        # Watchlist/Likes
        watchlist_entries = list(db.userwatchlists.find({}, {"_id": 0, "movie_id": 1}))
        for entry in watchlist_entries:
            history_ids.add(entry["movie_id"])
            
        # Ratings
        if "ratings" in db.list_collection_names():
            rating_entries = list(db.ratings.find({}, {"_id": 0, "movieId": 1}))
            for entry in rating_entries:
                history_ids.add(entry["movieId"])
        
        print(f"[ml-service] Found {len(history_ids)} movies in user histories")
        
        # Fetch details for any history movie not already in our pool
        added_count = 0
        for mid in history_ids:
            if mid not in movies_dict:
                details = fetch_movie_details(mid)
                if details:
                    movies_dict[mid] = details
                    added_count += 1
        
        if added_count > 0:
            print(f"[ml-service] Added {added_count} history movies to the pool")
            
    except Exception as e:
        print(f"[ml-service] WARNING: History movie fetch failed: {e}")
            
    all_movies = list(movies_dict.values())
    print(f"[ml-service] Total unique movies in diverse pool: {len(all_movies)}")
    return all_movies


def get_all_genres():
    """Load genres from TMDB API."""
    return fetch_genre_list()


def get_movie_genres():
    """
    Build movie-genre mappings from TMDB movie data.
    Returns a dict: movie_id -> list of genre_ids
    """
    # This is called separately, but we can reuse the same logic
    # or just return an empty map and let the models handle it
    return {}


def get_user_preferences(user_id: str):
    """
    Load a user's genre preferences from 'userpreferences' collection.
    Returns a dict: genre_id -> score
    """
    db = get_database()
    prefs = list(db.userpreferences.find(
        {"user_id": ObjectId(user_id)},
        {"_id": 0, "genre_id": 1, "score": 1}
    ))
    return {p["genre_id"]: p["score"] for p in prefs}


def get_user_watchlist(user_id: str):
    """
    Load a user's watchlist/ratings from 'userwatchlists' collection.
    Returns a list of dicts with movie_id, status, rating.
    """
    db = get_database()
    entries = list(db.userwatchlists.find(
        {"user_id": ObjectId(user_id)},
        {"_id": 0, "movie_id": 1, "status": 1, "rating": 1}
    ))
    return entries


def get_all_user_ratings():
    """
    Load ALL user ratings across all users for collaborative filtering.
    Returns: list of dicts with user_id (str), movie_id (int), rating (float).
    """
    db = get_database()

    # Gather from userwatchlists (status='rated' or 'liked')
    watchlist_ratings = list(db.userwatchlists.find(
        {"status": {"$in": ["rated", "liked"]}},
        {"_id": 0, "user_id": 1, "movie_id": 1, "rating": 1, "status": 1}
    ))

    # Also gather from the 'ratings' collection if it exists
    ratings_from_collection = []
    if "ratings" in db.list_collection_names():
        ratings_from_collection = list(db.ratings.find(
            {},
            {"_id": 0, "userId": 1, "movieId": 1, "rating": 1}
        ))

    # Normalize to a common format
    all_ratings = []
    for r in watchlist_ratings:
        rating_val = 10.0 if r["status"] == "liked" else float(r.get("rating") or 5.0)
        all_ratings.append({
            "user_id": str(r["user_id"]),
            "movie_id": r["movie_id"],
            "rating": rating_val
        })

    for r in ratings_from_collection:
        all_ratings.append({
            "user_id": str(r["userId"]),
            "movie_id": r["movieId"],
            "rating": float(r["rating"])
        })

    return all_ratings


def get_user_rated_movies(user_id: str):
    """
    Get movies that a specific user has rated, with their ratings.
    Returns: dict of movie_id -> rating
    """
    db = get_database()

    rated = {}

    # From watchlist (rated + disliked + liked)
    watchlist = list(db.userwatchlists.find(
        {
            "user_id": ObjectId(user_id),
            "status": {"$in": ["rated", "disliked", "liked"]}
        },
        {"_id": 0, "movie_id": 1, "rating": 1, "status": 1}
    ))
    for w in watchlist:
        if w["status"] == "disliked":
            rated[w["movie_id"]] = 1.0  # Treat as strongest possible negative signal
        elif w["status"] == "liked":
            rated[w["movie_id"]] = 10.0 # Treat 'liked' as max score for content-based seeding
        elif w.get("rating") is not None:
            rated[w["movie_id"]] = float(w["rating"])

    # From ratings collection
    if "ratings" in db.list_collection_names():
        user_ratings = list(db.ratings.find(
            {"userId": ObjectId(user_id)},
            {"_id": 0, "movieId": 1, "rating": 1}
        ))
        for r in user_ratings:
            rated[r["movieId"]] = float(r["rating"])

    return rated


def get_trending_movie_ids(limit=20):
    """Get top trending movie IDs from TMDB."""
    trending = fetch_trending_movies(limit)
    return [m["movie_id"] for m in trending]


def get_user_profile(user_id: str):
    """
    Load a user's profile preferences from the backend 'users' collection.
    Returns a dict with preferredLanguage, favoriteGenre, favoriteEra.
    """
    db = get_database()
    user = db.users.find_one(
        {"_id": ObjectId(user_id)},
        {
            "_id": 0,
            "preferredLanguage": 1,
            "favoriteGenre": 1,
            "favoriteEra": 1
        }
    )
    if not user:
        return {"preferredLanguage": "", "favoriteGenre": "", "favoriteEra": ""}

    return {
        "preferredLanguage": (user.get("preferredLanguage") or "").strip().lower(),
        "favoriteGenre": (user.get("favoriteGenre") or "").strip(),
        "favoriteEra": (user.get("favoriteEra") or "").strip()
    }
