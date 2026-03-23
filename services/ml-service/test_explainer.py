import sys; sys.path.append('c:\\Users\\Hemanth Vasudev N P\\OneDrive\\Desktop\\CineScope\\services\\ml-service');
from recommender import explainer;

recs = [
    {
        "movie_id": 123,
        "score": 0.8,
        "reason_type": "hybrid",
        "context": {
            "intersection_tier": 6,
            "intersection_reasons": ["Language", "Genre"]
        }
    }
]
movies_lookup = {123: {"title": "Test Movie", "language": "ta"}}
genre_names = {1: "Action"}
movie_genre_map = {123: [1]}

print("Calling explain_batch...")
try:
    explained = explainer.explain_batch(recs, movies_lookup, genre_names, movie_genre_map)
    print("Success!")
    print(explained[0]["explanation"])
except Exception as e:
    import traceback
    traceback.print_exc()
