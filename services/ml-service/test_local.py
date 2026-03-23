import sys; sys.path.append('c:\\Users\\Hemanth Vasudev N P\\OneDrive\\Desktop\\CineScope\\services\\ml-service');
import os; from dotenv import load_dotenv; load_dotenv();
from recommender.hybrid import initialize_models, get_hybrid_recommendations;
from database import get_database;
from bson import ObjectId;

print("[debug] Connecting to DB...")
db = get_database();
user = db.users.find_one({'email': 'hemantth06@outlook.com'});
if not user:
    print("[error] User not found"); sys.exit(1)

print(f"[debug] Initializing models (might take a bit)...")
initialize_models()

print(f"[debug] Fetching recommendations for {user['email']}...")
recs = get_hybrid_recommendations(str(user['_id']), limit=20)

print(f"\n--- RESULTS ({len(recs)}) ---")
for i, r in enumerate(recs):
    print(f"#{i+1}: {r['title']} | Lang: {r['language']} | Score: {r['score']} | Tier: {r.get('context', {}).get('intersection_tier')} | Reasons: {r.get('context', {}).get('intersection_reasons')}")
