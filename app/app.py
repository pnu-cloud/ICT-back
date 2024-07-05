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
        max_tokens=1024,
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

    return jsonify({"subject": subjects}), 200


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


@app.route('/subject/<int:subject_id>', methods=['GET'])
def get_subject(subject_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    subject = db.select_fetchone('select id, title, text from "subject" where subject_id=%s', [subject_id])

    return jsonify(subject), 200


@app.route('/subject/<int:subject_id>/chapter', methods=['GET'])
def chapter_list(subject_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    chapters = db.select_fetchall('select * from "chapter" where subject_id=%s order by id', [subject_id])

    return jsonify({"chapter": chapters}), 200


@app.route('/subject/<int:subject_id>/chapter', methods=['POST'])
def chapter_add(subject_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON data"}), 400

    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    chapter_id = db.execute_fetchone(
        'insert into "chapter"(subject_id, title, content) values (%s, %s, %s) RETURNING id',
        [subject_id, data['chapter'], data['contents']])[0]

    chapter = db.select_fetchone('select id, title, content from "chapter" where id=%s', [chapter_id])

    return jsonify(chapter), 200


@app.route('/subject/chapter/<int:chapter_id>', methods=['POST'])
def chapter_set(chapter_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON data"}), 400

    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    db.execute('update "chapter" set title=%s, content=%s where id=%s', [data['chapter'], data['contents'], chapter_id])

    chapter = db.select_fetchone('select id, title, content from "chapter" where id=%s', [chapter_id])

    return jsonify(chapter), 200


@app.route('/subject/chapter/<int:chapter_id>', methods=['DELETE'])
def chapter_del(chapter_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    db.execute('delete from "chapter" where id=%s', [chapter_id])

    return jsonify(), 200


@app.route('/subject/chapter/<int:chapter_id>', methods=['GET'])
def quiz_list(chapter_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    quiz_list = db.select_fetchall('select * from "quiz" where chapter_id=%s order by id', [chapter_id])

    return jsonify({"quiz": quiz_list}), 200


@app.route('/subject/chapter/<int:chapter_id>/quiz', methods=['POST'])
def quiz_create(chapter_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    quiz_id = db.execute_fetchone(
        'insert into "quiz"(chapter_id) values (%s) RETURNING id',
        [chapter_id])[0]

    chapter = db.select_fetchone('select id, title, content from "chapter" where id=%s', [chapter_id])

    gpt_assistant_prompt = """
학생이 특정 지식을 학습할 수 있도록 제공한 목차나 내용에 대해 문제를 생성해야 하는데 제공되는 언어에 상관없이 한국어로 문제를 출제해줘.
문제는 객관식이나 단답형 주관식을 적절히 섞어서 제작하고 추후 정답 확인이나 풀이는 별도로 질의할 예정이니 부가적인 설명은 생략하고 텍스트로만 이루어진 문제 본문만 작성해줘.
여러 문제를 생성하되 JSON 배열로 이루어지도록 결과를 생성해야 하고 문제 유형이나 보기를 별도로 JSON에 담지 말고 문제 본문 내에 함께 작성하고 문제 본문 앞에 숫자를 넣지말고 [문제 유형]을 넣어서 생생해줘 줄바꿈은 <br>로 하면 돼.
문제 유형은 (객관식: 주어진 보기에서 숫자 고르기) (단답형: 설명을 보고 특정한 단어를 작성) (주관식: 주어진 상황을 서술식으로 설명해야 하는 문제)이야.
출력 형식은 ["[객관식] 문제 내용", "[단답형] 문제 내용", "[주관식] 문제 내용"] 와 같이 이루어져야 해
    """
    gpt_user_prompt = chapter.get('content', "")

    results = generate_content(gpt_assistant_prompt, gpt_user_prompt)
    print(results)
    try:
        results = json.loads(results)
        for result in results:
            db.execute_fetchone(
            'insert into "problem"(quiz_id, question) values (%s, %s) RETURNING id',
            [quiz_id, result])
    except json.JSONDecodeError:
        db.execute_fetchone(
            'insert into "problem"(quiz_id, question) values (%s, %s) RETURNING id',
            [quiz_id, results])
        
    return jsonify({"quiz_id": quiz_id}), 200


@app.route('/subject/chapter/quiz/<int:quiz_id>', methods=['GET'])
def problem_list(quiz_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    problems = db.select_fetchall('select * from "problem" where quiz_id=%s order by id', [quiz_id])

    return jsonify({"problem": problems}), 200


@app.route('/subject/chapter/quiz/problem/<int:problem_id>', methods=['POST'])
def problem_submit(problem_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    problem = db.select_fetchone('select * from "problem" where id=%s', [problem_id])

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON data"}), 400

    gpt_assistant_prompt = """
제공하주는 question은 문제이고 user_answer은 학생이 제출한 답이야.
문제에 대해 학생에 제출한 답의 정답 유무를 확인하고,
맞은 경우 True만 출력하고 틀렸다면 틀렸다고 판단한 이유만 출력해줘.
    """
    gpt_user_prompt = f"문제: {problem['question']}\n학생 답안: {data['user_answer']}"
    print(gpt_user_prompt)

    result = generate_content(gpt_assistant_prompt, gpt_user_prompt)
    print(result)

    if (result == "True"):
        db.execute('update "problem" set user_answer=%s, is_correct=%s where id=%s', [data['user_answer'], True, problem_id])
    else:
        db.execute('update "problem" set user_answer=%s, is_correct=%s, feedback=%s where id=%s', [data['user_answer'], False, result, problem_id])

    problem = db.select_fetchone('select * from "problem" where id=%s', [problem_id])

    return jsonify(problem), 200


@app.route('/subject/chapter/quiz/problem/<int:problem_id>/solution', methods=['GET'])
def problem_solution(problem_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    problem = db.select_fetchone('select * from "problem" where id=%s', [problem_id])

    if problem['solution'] is None:
        gpt_assistant_prompt = """
    제공하주는 question은 문제이고 user_answer은 학생이 제출한 답이야.
    만약 틀렸다면 틀린 이유를 분석해주고 올바른 풀이를 작성해줘.
    만약 맞다면 문제에 관련된 정보를 제공하거나 다른 풀이 방법이 있다면 알려줘.
        """
        gpt_user_prompt = f"문제: {problem['question']}\n학생 답안: {problem['user_answer']}"
        print(gpt_user_prompt)

        result = generate_content(gpt_assistant_prompt, gpt_user_prompt)
        print(result)

        db.execute('update "problem" set solution=%s where id=%s', [result, problem_id])

        problem = db.select_fetchone('select * from "problem" where id=%s', [problem_id])

    return jsonify(problem), 200


@app.route('/quiz/<int:quiz_id>/subject')
def quiz2subject(quiz_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    subject = db.select_fetchone("""
SELECT s.*
FROM quiz q
JOIN chapter c ON q.chapter_id=c.id
JOIN subject s ON c.subject_id=s.id
WHERE q.id=%s;
    """, [quiz_id])

    return jsonify(subject), 200




@app.route('/dev/login', methods=['GET'])
def test_Login():
    session['user_id'] = 1
    return jsonify({"message": "임시 로그인 - user 1"}), 200

