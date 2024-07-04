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

from database import Database


app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['SESSION_COOKIE_SECURE'] = True

Session(app)

cors = CORS(app, resources={
  r"/*": {
        "origin": "ict.pnu.app", 
        "allow_headers": ["Content-Type", "Authorization"]
    },
}, supports_credentials=True)


API_KEY = os.getenv('OPENAI_API_KEY')
if not API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(api_key=API_KEY)


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


@app.route('/user', methods=['GET'])
def get_user():
    db = Database()
    if 'user_id' in session:
        user = db.select_fetchone('select * from "user" where id=%s', [session['user_id']])
        print(user)
        return jsonify(user), 200
     
    else:
        return jsonify({"message": "User not logged in"}), 403
    
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON data"}), 400
    db = Database()

    user = db.select_fetchone('select * from "user" where email=%s', [data['email']])
    if user is not None:
        return jsonify({"message": "이미 가입된 이메일입니다"}), 400

    user_id = db.execute_fetchone(
        'insert into "user"(email, password, name) values (%s, %s, %s) RETURNING id',
        [data['email'], data['password'], data['name']])[0]

    user = db.select_fetchone('select * from "user" where id=%s', [user_id])

    print(user)
    return jsonify(user), 200


@app.route('/signin', methods=['POST'])
def signin():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON data"}), 400
    db = Database()

    user = db.select_fetchone('select * from "user" where email=%s and password=%s', [data['email'], data['password']])
    if user is None:
        return jsonify({"message": "아이디 혹은 비밀번호가 일치하지 않습니다"}), 400

    session['user_id'] = user['id']
    return jsonify(user), 200


@app.route('/subject', methods=['GET'])
def subject_list():
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    subjects = db.select_fetchall('select * from "subject" where user_id=%s order by id', [user_id])

    return jsonify({"subject": [subjects]}), 200


@app.route('/subject', methods=['POST'])
def subject_add():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON data"}), 400

    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    subject_id = db.execute_fetchone(
        'insert into "subject"(user_id, title, text) values (%s, %s, %s) RETURNING id',
        [user_id, data['title'], data['text']])[0]

    subject = db.select_fetchone('select id, title, text from "subject" where id=%s', [subject_id])

    return jsonify(subject), 200





@app.route('/dev/login', methods=['GET'])
def test_Login():
    session['user_id'] = 1
    return jsonify({"message": "임시 로그인 - user 1"}), 200

