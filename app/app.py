from flask import Flask, session, request, jsonify, send_file
from flask_session import Session
from flask_cors import CORS
import psycopg2
import os
import io
import json
import threading


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


@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": "API SERVER"}), 200
