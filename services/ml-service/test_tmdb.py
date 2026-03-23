import sys; sys.path.append('c:\\Users\\Hemanth Vasudev N P\\OneDrive\Desktop\\CineScope\\services\\ml-service');
import os; from dotenv import load_dotenv; load_dotenv();
from tmdb_client import fetch_discover_movies;

print("Testing TMDB Discover for 'ta'...")
try:
    movies = fetch_discover_movies('ta', pages=1)
    print(f"Found {len(movies)} movies.")
    for m in movies[:5]:
        print(f"- {m['title']} ({m['language']}) pop={m['popularity']}")
except Exception as e:
    print(f"Error: {e}")
