import sys; sys.path.append('c:\\Users\\Hemanth Vasudev N P\\OneDrive\\Desktop\\CineScope\\services\\ml-service');
import os; 
from dotenv import load_dotenv; 
load_dotenv();
from database import get_database;
import requests, json;
db = get_database();
user = db.users.find_one({'email': 'hemantth06@outlook.com'});
uid = str(user['_id']);
res = requests.post('http://localhost:8000/recommend', json={'userId': uid, 'limit': 10}).json();
for i, r in enumerate(res['recommendations']):
    print(i+1, r['title'], '| Lang:', r['language'], '| Boost:', r.get('explanation', {}).get('boost', 'None'))
