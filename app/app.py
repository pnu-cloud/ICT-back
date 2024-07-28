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
from datetime import datetime, timedelta

from database import Database


app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['SESSION_COOKIE_SECURE'] = True

Session(app)

cors = CORS(app, resources={
  r"/*": {
        "origin": ["ict.pnu.app", "bict.pnu.app", "localhost:5500"],
        "allow_headers": ["Content-Type", "Authorization"]
    },
}, supports_credentials=True)


API_KEY = os.getenv('OPENAI_API_KEY')
if not API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(api_key=API_KEY)


def generate_content(gpt_assistant_prompt: str, gpt_user_prompt: str) -> str:
    gpt_prompt = f"{gpt_assistant_prompt} {gpt_user_prompt}"
    messages = [
        {"role": "assistant", "content": gpt_assistant_prompt},
        {"role": "user", "content": gpt_user_prompt}
    ]
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=1.0,
        max_tokens=1024,
        frequency_penalty=0.5
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
    subjects = db.select_fetchall('select * from "subject" where user_id=%s order by id DESC', [user_id])

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


@app.route('/subject/<int:subject_id>', methods=['PUT'])
def subject_update(subject_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON data"}), 400

    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    db.execute('update "subject" set title=%s, text=%s where id=%s', [data['title'], data['text'], subject_id])
    subject = db.select_fetchone('select * from "chapter" where id=%s', [subject_id])

    return jsonify(subject), 200


@app.route('/subject/<int:subject_id>', methods=['DELETE'])
def subject_del(subject_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    db.execute('delete from "subject" where id=%s', [subject_id])

    return jsonify(), 200



@app.route('/subject/<int:subject_id>/chapter', methods=['GET'])
def chapter_list(subject_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    chapters = db.select_fetchall('select * from "chapter" where subject_id=%s order by id', [subject_id])

    for chapter in chapters:
        chapter['content'] = chapter['content'].replace('\n', '<br>')

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

    # chapter = db.select_fetchone('select id, title, content, subject_id from "chapter" where id=%s', [chapter_id])
    chapter = db.select_fetchone('select * from "chapter" where id=%s', [chapter_id])

    db.execute("""
    update "subject" set progress=
        ((select sum(progress) from chapter where subject_id=%s) / (select count(*) from chapter where subject_id=%s))
        where id=%s
    """, [chapter['subject_id'], chapter['subject_id'], chapter['subject_id']])

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


@app.route('/subject/chapter/<int:chapter_id>', methods=['PUT'])
def chapter_update(chapter_id):
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

    chapter = db.select_fetchone('select id, title, content from "chapter" where id=%s', [chapter_id])

    gpt_assistant_prompt = """
학생이 학습한 내용을 스스로 평가할 수 있도록 제공한 목차나 내용으로 문제를 만들어야 해.
추후 정답 확인이나 풀이는 별도로 질의할 예정이니 부가적인 설명은 생략하고 문제 본문만 텍스트로 아래 주어진 형식대로 작성해줘.
여러 문제를 반환받아 파싱하기 위해 JSON 문자열 배열로 이루어지도록 결과를 생성해야 하고 문제 유형이나 보기를 별도로 담지 말고 문제 본문 텍스트내에 함께 작성해줘.
문제 유형은 (객관식: 주어진 보기에서 숫자 고르기) (단답형: 설명을 보고 특정한 단어를 작성) (주관식: 주어진 상황을 서술식으로 설명해야 하는 문제)이야.
특히 객관식 문제는 동일한 보기가 중복되지 않고 답이 하나만 존재하도록 보기를 만들 때 유의해야 하고 틀린 보기는 유사한 도메인 단어로 작성해줘.
문제 본문 앞에 숫자를 넣지말고 [문제 유형]을 넣어서 생생해줘 그리고 문제 본문은 HTML을 이용해 꾸미거나 강조할 수 있고 줄바꿈은 <br>로 출력하면 돼.
따라서 응답 형식은 ["[객관식] 문제 내용", ..., "[단답형] 문제 내용", ..., "[주관식] 문제 내용"] 와 같이 JSON으로 파싱이 가능해야 해.

- 응답 형식: ["[유형] 문제 내용<br>보기", "[유형] 문제 내용" .... ]
    """
    gpt_user_prompt = chapter.get('content', "")

    results = generate_content(gpt_assistant_prompt, gpt_user_prompt)
    msg = results
    print(results)
    results = results[results.find('['):(results.rfind(']')+1)]
    try:
        results = json.loads(results)

        now = datetime.now() + timedelta(hours=9)

        quiz_id = db.execute_fetchone(
            'insert into "quiz"(chapter_id, title) values (%s, %s) RETURNING id',
            [chapter_id, now.strftime('%Y-%m-%d %H:%M')])[0]

        for result in results:
            db.execute(
            'insert into "problem"(quiz_id, question) values (%s, %s) RETURNING id',
            [quiz_id, result])

        db.execute('update "quiz" set total_count=(select count(*) from "problem" where quiz_id=%s) where id=%s', [quiz_id, quiz_id])

        quiz = db.select_fetchone('select * from "quiz" where id=%s', [quiz_id])

        return jsonify(quiz), 200
    except json.JSONDecodeError:
        return jsonify({"message": msg}), 421



@app.route('/subject/chapter/quiz/<int:quiz_id>', methods=['GET'])
def problem_list(quiz_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    problems = db.select_fetchall('select * from "problem" where quiz_id=%s order by id', [quiz_id])

    quiz = db.select_fetchone('select * from "quiz" where id=%s', [quiz_id])

    chapter = db.select_fetchone('select id, title, content from "chapter" where id=%s', [quiz['chapter_id']])

    return jsonify({"chapter": chapter, "quiz": quiz, "problem": problems}), 200


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
문제에 대해 학생에 제출한 답의 정답 유무를 확인해줘.
맞은 경우 True라는 문자열만 출력하고, 틀렸다면 틀렸다고 판단한 이유를 알려주고 정답은 서술하지 말아줘.
정답 여부 응답을 확인할 때 문자열 "True"와 단순 비교하여 판단하기 때문에 대소문자를 유의하고 다른 문자가 함께 포함되면 안돼.
틀린 이유를 작성한다면 학생 같이 대상을 지칭하지 말고 이유만 ~입니다 와 같이 서술해줘.
- 응답 형식(정답): True
- 응답 형식(오답): 틀렸다고 판단한 이유 서술 (정답 비공개)
    """
    gpt_user_prompt = f"문제: {problem['question']}\n학생 답안: {data['user_answer']}"
    print(gpt_user_prompt)

    result = generate_content(gpt_assistant_prompt, gpt_user_prompt)
    print(result)

    if "True" in result:
        db.execute('update "problem" set user_answer=%s, is_correct=%s where id=%s', [data['user_answer'], True, problem_id])
    else:
        db.execute('update "problem" set user_answer=%s, is_correct=%s, feedback=%s where id=%s', [data['user_answer'], False, result, problem_id])

    problem = db.select_fetchone('select * from "problem" where id=%s', [problem_id])

    db.execute('update "quiz" set submit_count=(select count(*) from "problem" where quiz_id=%s and user_answer is not null) where id=%s',
               [problem['quiz_id'], problem['quiz_id']])

    db.execute('update "quiz" set correct_count=(select count(*) from "problem" where quiz_id=%s and is_correct=True) where id=%s',
               [problem['quiz_id'], problem['quiz_id']])

    db.execute("""
    update "quiz" set progress=
        (100 * (select count(*) from problem where quiz_id=%s and is_correct=True) / (select count(*) from problem where quiz_id=%s))
        where id=%s
    """, [problem['quiz_id'], problem['quiz_id'], problem['quiz_id']])

    quiz = db.select_fetchone('select * from "quiz" where id=%s', [problem['quiz_id']])

    db.execute("""  
    update "chapter" set progress=
        (select max(progress) from quiz where chapter_id=%s)
        where id=%s
    """, [quiz['chapter_id'], quiz['chapter_id']])

    chapter = db.select_fetchone('select * from "chapter" where id=%s', [quiz['chapter_id']])

    db.execute("""
    update "subject" set progress=
        ((select sum(progress) from chapter where subject_id=%s) / (select count(progress) from chapter where subject_id=%s))
        where id=%s
    """, [chapter['subject_id'], chapter['subject_id'], chapter['subject_id']])

    return jsonify(problem), 200


@app.route('/subject/chapter/quiz/problem/<int:problem_id>', methods=['DELETE'])
def problem_reset(problem_id):
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    db.execute('update "problem" set user_answer=%s, is_correct=%s, feedback=%s, solution=%s where id=%s',
               [None, None, None, None, problem_id])

    return ""


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
만약 맞다면 문제에 풀이에 학습에 도움이 될 수 있도록 관련된 정보를 제공하거나 다른 풀이 방법이 있다면 알려줘.
그리고 작성할 때는 학생 같이 대상을 지칭하지 말고 정보만 ~입니다 형식으로 서술해줘.
응답받은 내용은 HTML 형식으로 출력할거라 HTML 태그를 사용해서 강조하거나 색상을 넣는 등 보기 좋게 만들어주면 좋아.
        """
        gpt_user_prompt = f"문제: {problem['question']}\n학생 답안: {problem['user_answer']}"
        print(gpt_user_prompt)

        result = generate_content(gpt_assistant_prompt, gpt_user_prompt).replace('\n', "<br>")
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


@app.route('/wrong')
def get_wrong():
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    wrong = db.select_fetchall("""
    SELECT p.*, c.subject_id, q.chapter_id, p.quiz_id, s.title as subject_title, c.title as chapter_title, q.title as quiz_title
    FROM "user" u
    JOIN subject s ON u.id = s.user_id
    JOIN chapter c ON s.id = c.subject_id
    JOIN quiz q ON s.id = q.chapter_id
    JOIN problem p ON q.id=p.quiz_id
    WHERE u.id=%s and p.is_correct=FALSE;
        """, [user_id])
    return jsonify(wrong), 403


@app.route('/grade')
def get_grade():
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify({"message": "Invalid session or not logged in"}), 403

    db = Database()
    grade = {}

    grade['subject'] = db.select_fetchall("""
        SELECT *
        FROM "subject"
        WHERE user_id=%s;
            """, [user_id])

    for subject in grade['subject']:
        subject['total_count'] = 0
        subject['submit_count'] = 0
        subject['correct_count'] = 0

        subject['chapter'] = db.select_fetchall("""
        SELECT *
        FROM "chapter"
        WHERE subject_id=%s;
            """, [subject['id']])

        for chapter in subject['chapter']:
            count = db.select_fetchone("""
            SELECT sum(total_count) as total_count, sum(submit_count) as submit_count, sum(correct_count) as correct_count
            FROM "quiz"
            WHERE chapter_id=%s;
                """, [chapter['id']])

            if count['total_count'] is not None:
                chapter['total_count'] = count['total_count']
                chapter['submit_count'] = count['submit_count']
                chapter['correct_count'] = count['correct_count']

                subject['total_count'] += chapter['total_count']
                subject['submit_count'] += chapter['submit_count']
                subject['correct_count'] += chapter['correct_count']

    return jsonify(grade), 200


@app.route('/dev/login', methods=['GET'])
def test_Login():
    session['user_id'] = 1
    return jsonify({"message": "임시 로그인 - user 1"}), 200

