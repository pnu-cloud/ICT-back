from flask import Flask, session, request, jsonify, send_file
from flask_session import Session
from flask_cors import CORS
import psycopg2
import os
import io
import json
import threading
import weave
from openai import OpenAI
import pandas as pd
import time


app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['SESSION_COOKIE_SECURE'] = True

Session(app)

cors = CORS(app, resources={
  r"/api/*": {
        "origin": "ict.pnu.app", 
        "allow_headers": ["Content-Type", "Authorization"]
    },
}, supports_credentials=True)


API_KEY = os.getenv('OPENAI_API_KEY')
if not API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(api_key=API_KEY)

def get_db_connection():
    return psycopg2.connect(os.environ['DATABASE_URL'])

def execute_query(query, args=(), fetchone=False, fetchall=False, commit=False):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, args)
    result = None
    if fetchone:
        result = cur.fetchone()
    elif fetchall:
        result = cur.fetchall()
    if commit:
        conn.commit()
    cur.close()
    conn.close()
    return result

def generate_content(gpt_assistant_prompt: str, gpt_user_prompt: str) -> dict:
    gpt_prompt = f"{gpt_assistant_prompt} {gpt_user_prompt}"
    messages = [
        {"role": "assistant", "content": gpt_assistant_prompt},
        {"role": "user", "content": gpt_user_prompt}
    ]
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.2,
        max_tokens=10000,
        frequency_penalty=0.0
    )
    response_text = response.choices[0].message.content
    tokens_used = response.usage.total_tokens
    
    return response_text


@app.route('/', methods=['GET'])
def index():
    gpt_assistant_prompt = "학생들이 내용을 입력하면 관련된 내용으로 문제를 만들고 풀이를 제공해야 해. 주어진 내용에 대한 문제를 만들어줘"
    gpt_user_prompt = "컴퓨터 알고리즘 - 정렬"
    
    result = generate_content(gpt_assistant_prompt, gpt_user_prompt)
    return jsonify(result), 200