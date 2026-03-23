import sys; sys.path.append('c:\\Users\\Hemanth Vasudev N P\\OneDrive\\Desktop\\CineScope\\services\\ml-service');
import os; from dotenv import load_dotenv; load_dotenv();
from database import get_database;
import requests, json;
db = get_database();
user = db.users.find_one({'email': 'hemantth06@outlook.com'});
uid = str(user['_id']);
print(f"User: {user['email']} (ID: {uid})")
print(f"Profile: Lang={user.get('preferredLanguage')}, Genre={user.get('favoriteGenre')}, Era={user.get('favoriteEra')}")

# Call the API
res = requests.post('http://localhost:8000/recommend', json={'userId': uid, 'limit': 20}).json()
print(f"Strategy used: {res.get('meta', {}).get('strategy')}")
print(f"Pool size in _movies_lookup (approx): {len(res.get('recommendations', []))}") # Not useful directly but let's see results

print("\n--- TOP RECOMMENDATIONS ---")
for i, r in enumerate(res.get('recommendations', [])):
    print(f"#{i+1}: {r['title']} | Lang: {r['language']} | Release: {r['release_date']} | Boost: {r.get('explanation', {}).get('boost', 'None')}")

# Check if any Tamil movies are in the full lookup (via a backdoor if possible, or just checking if they exist)
# Actually, let's just grep the logs if we can.
