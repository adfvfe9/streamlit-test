import streamlit as st
import json
import hashlib
import os
import random
import time
import asyncio
import httpx
from datetime import datetime
from streamlit_ace import st_ace # 전문 코드 에디터 라이브러리 import
import re # 난이도 숫자 추출을 위해 import

# --- 페이지 기본 설정 ---
st.set_page_config(
    page_title="코딩 마스터",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 데이터 파일 및 API 제한 설정 ---
USER_DATA_FILE = "users.json"
PROBLEM_DATA_FILE = "problems.json"
API_USAGE_FILE = "api_usage.json"
# Gemini 2.5 Flash 무료 등급 기준(250 RPD)보다 안전하게 설정
DAILY_API_LIMIT = 200
# Gemini 2.5 Flash 무료 등급 기준(10 RPM)
RPM_LIMIT = 10

# --- API 사용량 추적 기능 ---
def load_api_usage():
    """오늘 날짜의 API 사용량을 로드하고, 날짜가 다르면 초기화합니다."""
    today = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(API_USAGE_FILE):
        return {"date": today, "daily_count": 0, "timestamps": []}

    try:
        with open(API_USAGE_FILE, "r") as f:
            usage_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"date": today, "daily_count": 0, "timestamps": []}

    # 날짜가 바뀌면 사용량 초기화
    if usage_data.get("date") != today:
        usage_data = {"date": today, "daily_count": 0, "timestamps": []}
        save_api_usage(usage_data)

    # 1분이 지난 타임스탬프 제거
    current_time = time.time()
    usage_data["timestamps"] = [t for t in usage_data.get("timestamps", []) if current_time - t < 60]

    return usage_data

def save_api_usage(usage_data):
    """API 사용량을 파일에 저장합니다."""
    with open(API_USAGE_FILE, "w") as f:
        json.dump(usage_data, f, indent=4)

@st.cache_data
def load_problems():
    if not os.path.exists(PROBLEM_DATA_FILE):
        default_problems = {"skill_test": {"Python": [], "C": [], "Java": []}}
        with open(PROBLEM_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default_problems, f, indent=4)
    with open(PROBLEM_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_users():
    if not os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "w") as f: json.dump({}, f)

    try:
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {} # 파일이 비어있으면 빈 딕셔너리 반환

def save_users(users_data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(users_data, f, indent=4)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

problems_db = load_problems()

# --- UI 스타일링 ---
def apply_custom_style():
    st.markdown("""
        <style>
            .main-title { text-align: center; font-size: 3rem; font-weight: bold; margin-bottom: 20px; }
            .problem-card { background-color: #262730; border-radius: 10px; padding: 20px; margin: 10px 0; border: 1px solid #444; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
            .problem-card h3 { color: #1E90FF; margin-bottom: 15px; }
            .problem-card p { font-size: 1.1rem; }
            .problem-card .points { text-align: right; font-size: 1.2rem; font-weight: bold; color: #FFD700; }
            .signup-success { background-color: #28a745; color: white; padding: 20px; border-radius: 10px; text-align: center; font-size: 1.2rem; margin-bottom: 20px; }
        </style>
    """, unsafe_allow_html=True)

# --- Gemini API를 이용한 AI 기능 ---
async def call_gemini_api(prompt, response_schema):
    # st.secrets를 사용하여 API 키를 안전하게 불러옵니다.
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except FileNotFoundError:
        st.error("`.streamlit/secrets.toml` 파일을 찾을 수 없습니다. 프로젝트에 `.streamlit/secrets.toml` 파일을 생성하고 API 키를 추가해주세요.")
        return None
    except KeyError:
        st.error("`.streamlit/secrets.toml` 파일에 `GEMINI_API_KEY`를 설정해주세요.")
        return None

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=payload, timeout=90)
            response.raise_for_status()
            result = response.json()
            response_text = result['candidates'][0]['content']['parts'][0]['text']
            return json.loads(response_text)
    except Exception as e:
        print(f"API Error: {e}")
        st.error(f"API 호출 중 오류가 발생했습니다: {e}")
        return None

async def grade_with_ai_real(user_code, problem, language):
    prompt = f"""You are an expert programming tutor. Evaluate a user's code for a given problem.
    Language: {language}, Problem: "{problem['title']}" - {problem['description']}
    User's Code: ```{language}\n{user_code}\n```
    Respond ONLY in JSON format with two keys: "is_correct" (boolean) and "feedback" (a brief, helpful explanation in Korean)."""
    schema = {
        "type": "OBJECT",
        "properties": { "is_correct": {"type": "BOOLEAN"}, "feedback": {"type": "STRING"} },
        "required": ["is_correct", "feedback"]
    }

    parsed_response = await call_gemini_api(prompt, schema)
    if parsed_response:
        return parsed_response.get("is_correct", False), parsed_response.get("feedback", "AI 응답 처리 실패")
    return False, "AI 채점 중 오류 발생. API 키 또는 네트워크를 확인해주세요."

async def generate_ai_problem(language, level):
    level_map = {
        "Level 1: 기초 문법": "very basic syntax", "Level 2: 자료 구조": "basic data structures",
        "Level 3: 알고리즘": "fundamental algorithms", "Level 4: 심화": "complex topics",
        "Level 5: 전문가": "advanced topics"
    }
    topic = level_map.get(level, "general programming concepts")

    lang_instruction = ""
    if language == "Java":
        lang_instruction = "CRITICAL INSTRUCTION FOR JAVA: For the 'function_stub', you MUST provide the full method signature including `public`, return type and parameters (e.g., `public int solution(int n)`, `public String[] solution(String[] words)`). You MUST use primitive array types (e.g., `int[] arr`) instead of Collection types like `List<String>`."
    elif language == "C":
        lang_instruction = "CRITICAL INSTRUCTION FOR C: For the 'function_stub', you MUST provide the full function signature including return type and parameters (e.g., `int solution(int n)`, `char* solution(char* s)`)."


    prompt = f"""Create a new, unique programming problem for a user learning {language}.
    The topic should be about {topic}.
    The problem must be solvable within a single function.
    {lang_instruction}

    Respond ONLY in JSON format with the following keys:
    - "id": A unique string identifier (e.g., "AI_PY_L1_...")
    - "title": A short, descriptive title in Korean.
    - "description": A clear problem description in Korean.
    - "function_stub": The function name and its parameters. For Python, no keywords or types (e.g., "solution(n)"). For C and Java, the full method signature.
    - "example_input": A simple, clear example of input.
    - "example_output": The corresponding output for the example input.
    - "relative_difficulty": An integer from 1 (very easy for this level) to 5 (very hard for this level) based on your assessment of the problem's complexity.
    """

    schema = {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "STRING"}, "title": {"type": "STRING"}, "description": {"type": "STRING"},
            "function_stub": {"type": "STRING"},
            "example_input": {"type": "STRING"}, "example_output": {"type": "STRING"},
            "relative_difficulty": {"type": "INTEGER"}
        },
        "required": ["id", "title", "description", "function_stub", "example_input", "example_output", "relative_difficulty"]
    }

    problem_data = await call_gemini_api(prompt, schema)
    if problem_data:
        level_num_match = re.search(r'Level (\d+)', level)
        level_num = int(level_num_match.group(1)) if level_num_match else 1
        base_points = level_num * 10

        relative_difficulty = problem_data.get("relative_difficulty", 3)
        adjustment_factor = (relative_difficulty - 3) * 0.25

        final_points = int(base_points * (1 + adjustment_factor))
        problem_data['points'] = max(5, final_points)

    return problem_data


async def get_ai_hint(problem, language):
    """AI를 이용해 문제에 대한 힌트를 생성합니다."""
    prompt = f"""You are a helpful programming tutor. A user is stuck on a problem and needs a hint.
    Provide a concise, useful hint in Korean for the following problem, but DO NOT give away the direct answer.
    Guide them towards the right approach or concept.

    Language: {language}
    Problem Title: {problem['title']}
    Problem Description: {problem['description']}

    Respond ONLY in JSON format with one key: "hint" (string)."""

    schema = {"type": "OBJECT", "properties": {"hint": {"type": "STRING"}}, "required": ["hint"]}

    parsed_response = await call_gemini_api(prompt, schema)
    if parsed_response:
        return parsed_response.get("hint", "힌트를 생성하는 데 실패했습니다.")
    return "힌트 생성 중 오류가 발생했습니다."


# --- UI 컴포넌트 ---
def show_login_signup_page():
    st.markdown('<p class="main-title">코딩 마스터에 오신 것을 환영합니다</p>', unsafe_allow_html=True)
    if st.session_state.get('signup_success', False):
        st.markdown('<div class="signup-success">✅ 회원가입 완료! 로그인하여 학습을 시작하세요.</div>', unsafe_allow_html=True)
        del st.session_state.signup_success

    col1, col2 = st.columns(2)
    with col1:
        with st.form("login_form"):
            st.header("로그인")
            username = st.text_input("사용자 이름")
            password = st.text_input("비밀번호", type="password")
            login_button = st.form_submit_button("로그인")

        if login_button:
            users = load_users()
            if username in users and users[username]["password"] == hash_password(password):
                st.session_state.logged_in = True
                st.session_state.username = username
                user_data = users[username]
                user_data.setdefault('solved_problems', []); user_data.setdefault('total_score', 0)
                st.session_state.user_info = user_data
                st.rerun()
            else:
                st.error("사용자 이름 또는 비밀번호가 잘못되었습니다.")
    with col2:
        with st.form("signup_form"):
            st.header("회원가입")
            new_username = st.text_input("새 사용자 이름")
            new_password = st.text_input("새 비밀번호", type="password")
            signup_button = st.form_submit_button("회원가입")

        if signup_button:
            users = load_users()
            if new_username in users: st.error("이미 존재하는 사용자 이름입니다.")
            elif not new_username or not new_password: st.warning("모든 필드를 입력해주세요.")
            else:
                users[new_username] = {"password": hash_password(new_password), "skill_test_taken": False, "language": None, "level": None, "solved_problems": [], "total_score": 0}
                save_users(users)
                st.session_state.signup_success = True
                st.rerun()

def run_skill_test(language):
    st.header(f"'{language}' 기초 실력 테스트")
    if 'test_completed' in st.session_state:
        st.success(f"테스트 완료! {st.session_state.test_total_questions}문제 중 {st.session_state.test_score}문제를 맞혔습니다.")
        st.balloons()
        st.info(f"당신의 레벨은 '{st.session_state.user_info['level']}'로 측정되었습니다.")
        if st.button("학습 시작하기"):
            for key in list(st.session_state.keys()):
                if key.startswith('test_'): del st.session_state[key]
            st.rerun()
        return

    questions = problems_db["skill_test"].get(language, [])
    with st.form("skill_test_form"):
        user_answers = [st.radio(q["question"], q["options"], key=f"q{i}") for i, q in enumerate(questions)]
        submitted = st.form_submit_button("결과 확인하기")

    if submitted:
        score = sum(1 for i, ua in enumerate(user_answers) if ua == questions[i]["answer"])
        levels = ["Level 1: 기초 문법", "Level 2: 자료 구조", "Level 3: 알고리즘", "Level 4: 심화", "Level 5: 전문가"]
        score_percent = (score / len(questions)) * 100 if questions else 0
        level_index = min(len(levels) - 1, int(score_percent // 20))
        level = levels[level_index]

        users = load_users()
        user = users[st.session_state["username"]]

        user.update({"skill_test_taken": True, "language": language, "level": level})
        save_users(users)
        st.session_state.user_info = user
        st.session_state.test_score, st.session_state.test_total_questions = score, len(questions)
        st.session_state.test_completed = True
        st.rerun()

def show_dashboard():
    user_info = st.session_state.user_info
    st.sidebar.header(f"🧑‍💻 {st.session_state.username}님")
    st.sidebar.metric("총 획득 점수", f"{user_info.get('total_score', 0)} 점")

    api_usage = load_api_usage()
    st.sidebar.metric("오늘 AI 사용량", f"{api_usage['daily_count']} / {DAILY_API_LIMIT} 회")
    st.sidebar.metric("분당 AI 사용량", f"{len(api_usage['timestamps'])} / {RPM_LIMIT} 회")


    st.sidebar.divider()
    st.sidebar.subheader("학습 설정")

    languages = ["Python", "C", "Java"]
    new_lang = st.sidebar.selectbox("학습 언어 변경", languages, index=languages.index(user_info['language']))
    level_options = ["Level 1: 기초 문법", "Level 2: 자료 구조", "Level 3: 알고리즘", "Level 4: 심화", "Level 5: 전문가"]
    try: current_level_index = level_options.index(user_info['level'])
    except ValueError: current_level_index = 0
    new_level = st.sidebar.selectbox("난이도 변경", level_options, index=current_level_index)

    if st.sidebar.button("설정 저장", use_container_width=True):
        users = load_users()
        user = users[st.session_state.username]
        user['language'], user['level'] = new_lang, new_level
        save_users(users)
        st.session_state.user_info = user
        st.session_state.current_problem = None
        st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("로그아웃", use_container_width=True): st.session_state.clear(); st.rerun()

    st.markdown(f'<p class="main-title">"{user_info["language"]}" 학습 대시보드</p>', unsafe_allow_html=True)
    st.info(f"현재 **{user_info['level']}** 레벨의 문제를 풀고 있습니다.")

    api_usage = load_api_usage()
    is_limit_reached = api_usage['daily_count'] >= DAILY_API_LIMIT or len(api_usage['timestamps']) >= RPM_LIMIT

    # --- 채점 결과가 있으면 표시 ---
    if 'grading_result' in st.session_state:
        result = st.session_state.grading_result
        if result['correct']:
            st.success(f"채점 결과: {result['feedback']}")
            st.info(f"{result['points_awarded']}점을 획득했습니다! 총 점수: {user_info['total_score']}점")
            st.balloons()
        else:
            st.error(f"채점 결과: {result['feedback']}")

        if st.button("다음 문제로", type="primary"):
            del st.session_state.grading_result
            st.rerun()
        return # 채점 결과를 보여줄 때는 문제 생성 버튼 등을 숨김

    # --- 새 문제 생성 버튼 ---
    if st.button("🤖 AI로 새로운 문제 생성하기", type="primary", use_container_width=True, disabled=is_limit_reached):
        if is_limit_reached:
            st.toast("API 호출 한도에 도달했습니다. 잠시 후 다시 시도해주세요.", icon="🚨")
        else:
            with st.spinner("AI가 당신만을 위한 새로운 문제를 만들고 있습니다..."):
                problem = asyncio.run(generate_ai_problem(user_info['language'], user_info['level']))

            if problem:
                api_usage['daily_count'] += 1
                api_usage['timestamps'].append(time.time())
                save_api_usage(api_usage)
                st.session_state.current_problem = problem
                st.session_state.current_problem_points = problem['points']
                if 'current_hint' in st.session_state: del st.session_state.current_hint # 새 문제 생성 시 이전 힌트 제거
            else:
                st.error("문제 생성에 실패했습니다. 잠시 후 다시 시도해주세요.")
            st.rerun()
    elif is_limit_reached:
        st.warning("AI 기능이 일시적으로 비활성화되었습니다. (호출 제한 도달)")


    if "current_problem" in st.session_state and st.session_state.current_problem:
        problem = st.session_state.current_problem
        points = st.session_state.get('current_problem_points', problem.get('points', 5))
        st.markdown(f"""<div class="problem-card">
            <p class="points">획득 가능 점수: {points} / {problem.get('points', 5)} 점</p>
            <h3>{problem.get('title', 'No Title')}</h3> <p>{problem.get('description', 'No Description')}</p><hr>
            <b>입력 예시:</b><pre><code>{problem.get('example_input', '')}</code></pre>
            <b>출력 예시:</b><pre><code>{problem.get('example_output', '')}</code></pre>
            </div>""", unsafe_allow_html=True)

        # --- 힌트 표시 및 닫기 ---
        if 'current_hint' in st.session_state and st.session_state.current_hint:
            cols = st.columns([10, 1])
            with cols[0]:
                st.info(f"💡 AI 힌트: {st.session_state.current_hint}")
            with cols[1]:
                if st.button("X", key="close_hint"):
                    del st.session_state.current_hint
                    st.rerun()

        hint_cost = max(5, int(user_info.get('total_score', 0) * 0.1))

        if st.button(f"💡 힌트 보기 ({hint_cost}점 소모)", disabled=is_limit_reached):
            if user_info.get('total_score', 0) < hint_cost:
                st.warning(f"힌트를 보려면 최소 {hint_cost}점이 필요합니다.")
            elif is_limit_reached:
                st.toast("API 호출 한도에 도달했습니다. 잠시 후 다시 시도해주세요.", icon="🚨")
            else:
                with st.spinner("AI가 힌트를 생성 중입니다..."):
                    hint_text = asyncio.run(get_ai_hint(problem, user_info['language']))

                api_usage = load_api_usage()
                api_usage['daily_count'] += 1
                api_usage['timestamps'].append(time.time())
                save_api_usage(api_usage)
                users = load_users()
                user = users[st.session_state.username]
                user['total_score'] = user.get('total_score', 0) - hint_cost
                save_users(users)
                st.session_state.user_info = user

                st.session_state.current_hint = hint_text
                st.toast(f"{hint_cost}점을 사용하여 힌트를 얻었습니다!", icon="💰")
                st.rerun()

        language = user_info['language']
        lang_map = {"Python": "python", "C": "c_cpp", "Java": "java"}

        function_stub = problem.get("function_stub", "solution()")
        clean_stub = function_stub.replace("def ", "").replace(":", "").strip()

        if language == "Python":
            template = f"def {clean_stub}:\n    answer = 0\n    return answer"
        elif language == "C":
            template = f"{clean_stub} {{\n    int answer = 0;\n    return answer;\n}}"
        elif language == "Java":
            template = f"""class Solution {{
    {clean_stub} {{
        int answer = 0;
        return answer;
    }}
}}
"""
        else:
            template = ""

        editor_key = f"ace_editor_{problem.get('id')}_{language}"

        user_code = st_ace(
            value=st.session_state.get(editor_key, template),
            language=lang_map.get(language, "text"),
            theme="tomorrow_night_blue", keybinding="vscode", font_size=14,
            height=300, wrap=True, auto_update=True,
            key=editor_key
        )

        if st.button("AI에게 채점받기"):
            # st.session_state[editor_key] = user_code # <- THIS LINE IS REMOVED
            if not user_code.strip(): st.warning("코드를 입력해주세요.")
            else:
                api_usage = load_api_usage()
                if api_usage['daily_count'] >= DAILY_API_LIMIT or len(api_usage['timestamps']) >= RPM_LIMIT:
                    st.error("API 호출 한도에 도달했습니다. 잠시 후 다시 시도해주세요.")
                else:
                    with st.spinner("AI가 코드를 채점 중입니다..."):
                        is_correct, feedback = asyncio.run(grade_with_ai_real(user_code, problem, user_info['language']))

                    api_usage['daily_count'] += 1
                    api_usage['timestamps'].append(time.time())
                    save_api_usage(api_usage)

                    if is_correct:
                        users = load_users()
                        user = users[st.session_state.username]
                        user['solved_problems'].append(problem['id'])
                        user['total_score'] = user.get('total_score', 0) + points
                        save_users(users)
                        st.session_state.user_info = user

                        st.session_state.grading_result = {"correct": True, "feedback": feedback, "points_awarded": points}

                        del st.session_state.current_problem
                        if 'current_problem_points' in st.session_state: del st.session_state.current_problem_points
                        if 'current_hint' in st.session_state: del st.session_state.current_hint
                        st.rerun()
                    else:
                        st.session_state.grading_result = {"correct": False, "feedback": feedback}
                        penalty = int(problem.get('points', 5) * 0.2)
                        st.session_state.current_problem_points = max(0, points - penalty)
                        st.rerun()

# --- 메인 앱 로직 ---
def main():
    apply_custom_style()
    if "logged_in" not in st.session_state: st.session_state.logged_in = False

    if st.session_state.logged_in:
        if not st.session_state.user_info.get("skill_test_taken"):
            st.header("🚀 학습 시작 전, 실력부터 측정해볼까요?")
            lang = st.selectbox("학습하고 싶은 언어를 선택하세요:", ["Python", "C", "Java"])
            if st.button(f"'{lang}' 실력 테스트 시작하기", use_container_width=True, type="primary"):
                st.session_state.start_test = True
                st.session_state.test_language = lang
                st.rerun()
            if st.session_state.get('start_test', False):
                run_skill_test(st.session_state.test_language)
        else:
            show_dashboard()
    else:
        show_login_signup_page()

if __name__ == "__main__":
    main()
