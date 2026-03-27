"""
CineScope ML Service — Database & Data Connector

Connects to MongoDB for user-specific data (ratings, preferences, watchlists).
Movie data is fetched from TMDB API instead of a local MongoDB collection.
"""

import os
from pymongo import MongoClient
from bson import ObjectId
from tmdb_client import fetch_popular_movies, fetch_trending_movies, fetch_genre_list

_client = None
_db = None


def get_database():
    """Get or create the MongoDB connection."""
    global _client, _db
    if _db is not None:
        return _db

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/cinescope")
    _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    _db = _client.get_default_database(default="test")
    _client.admin.command("ping")
    print("[ml-service] MongoDB connected")
    return _db


def get_all_movies():
    """
    Load movies from TMDB (popular movies across multiple pages).
    Returns a list of dicts with movie_id, title, overview, genres, etc.
    """
    print("[ml-service] Fetching movies from TMDB...")
    movies = fetch_popular_movies(pages=10)
    print(f"[ml-service] Fetched {len(movies)} movies from TMDB")
    return movies


def get_all_genres():
    """Load genres from TMDB API."""
    return fetch_genre_list()


def get_movie_genres():
    """
    Build movie-genre mappings from TMDB movie data.
    Returns a dict: movie_id -> list of genre_ids
    """
    movies = fetch_popular_movies(pages=10)
    movie_genre_map = {}
    for m in movies:
        mid = m["movie_id"]
        genre_ids = m.get("genre_ids", [])
        if genre_ids:
            movie_genre_map[mid] = genre_ids
    return movie_genre_map


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

    # Gather from userwatchlists (status='rated' with a rating)
    watchlist_ratings = list(db.userwatchlists.find(
        {"status": "rated", "rating": {"$ne": None}},
        {"_id": 0, "user_id": 1, "movie_id": 1, "rating": 1}
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
        all_ratings.append({
            "user_id": str(r["user_id"]),
            "movie_id": r["movie_id"],
            "rating": float(r["rating"])
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

    # From watchlist (rated + disliked)
    watchlist = list(db.userwatchlists.find(
        {
            "user_id": ObjectId(user_id),
            "status": {"$in": ["rated", "disliked"]}
        },
        {"_id": 0, "movie_id": 1, "rating": 1, "status": 1}
    ))
    for w in watchlist:
        if w["status"] == "disliked":
            rated[w["movie_id"]] = 1.0  # Treat as strongest possible negative signal
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
