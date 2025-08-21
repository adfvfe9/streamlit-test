import streamlit as st
import json
import hashlib
import os
import random
import time
import asyncio
import httpx # Streamlit의 클라우드 환경에서 API 요청을 위해 필요할 수 있습니다.

# --- 페이지 기본 설정 ---
st.set_page_config(
    page_title="코딩 마스터",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 데이터 파일 관리 ---
USER_DATA_FILE = "users.json"
PROBLEM_DATA_FILE = "problems.json"

# 사용자 데이터 로드 또는 생성
def load_users():
    if not os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(USER_DATA_FILE, "r") as f:
        return json.load(f)

# 사용자 데이터 저장
def save_users(users_data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(users_data, f, indent=4)

# 문제 데이터 로드
def load_problems():
    with open(PROBLEM_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# 비밀번호 해싱
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 문제 데이터 로드 (앱 실행 시 한 번만)
problems_db = load_problems()

# --- UI 스타일링 ---
def apply_custom_style():
    st.markdown("""
        <style>
            .main-title { text-align: center; font-size: 3rem; font-weight: bold; margin-bottom: 20px; }
            .problem-card { background-color: #262730; border-radius: 10px; padding: 20px; margin: 10px 0; border: 1px solid #444; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
            .problem-card h3 { color: #1E90FF; margin-bottom: 15px; }
            .problem-card p { font-size: 1.1rem; }
            .problem-card .points { text-align: right; font-size: 1.2rem; font-weight: bold; color: #28a745; }
            .signup-success { background-color: #28a745; color: white; padding: 20px; border-radius: 10px; text-align: center; font-size: 1.2rem; margin-bottom: 20px; }
        </style>
    """, unsafe_allow_html=True)

# --- Gemini API를 이용한 AI 채점 ---
async def grade_with_ai_real(user_code, problem, language):
    """
    Gemini API를 호출하여 사용자의 코드를 실제로 채점합니다.
    """
    api_key = "AIzaSyBHuZrqrXFOiYfV0SDzmlvdjDXbX3LcM34" # 사용자 제공 API 키
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"

    prompt = f"""
    You are an expert programming tutor and code evaluator.
    A user has submitted a solution for a programming problem.
    Your task is to evaluate the code and determine if it correctly solves the problem.

    Programming Language: {language}

    Problem Title: {problem['title']}
    Problem Description: {problem['description']}

    User's Code:
    ```{language}
    {user_code}
    ```

    Please evaluate the user's code based on the problem description.
    Provide your response ONLY in JSON format according to the following schema.
    - "is_correct": A boolean value. Set to true if the code correctly solves the problem, otherwise false.
    - "feedback": A string containing a brief, helpful explanation for the user in Korean. If correct, praise them. If incorrect, provide a hint on how to fix it without giving away the direct answer.
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "is_correct": {"type": "BOOLEAN"},
                    "feedback": {"type": "STRING"}
                },
                "required": ["is_correct", "feedback"]
            }
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            response_text = result['candidates'][0]['content']['parts'][0]['text']
            parsed_response = json.loads(response_text)
            
            return parsed_response.get("is_correct", False), parsed_response.get("feedback", "AI 응답을 처리하는 데 실패했습니다.")

    except (httpx.HTTPStatusError, KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"API Error: {e}")
        return False, "AI 채점 중 오류가 발생했습니다. API 키 설정 또는 네트워크를 확인해주세요."


# --- UI 컴포넌트 ---

def show_login_signup_page():
    st.markdown('<p class="main-title">코딩 마스터에 오신 것을 환영합니다</p>', unsafe_allow_html=True)
    if st.session_state.get('signup_success', False):
        st.markdown('<div class="signup-success">✅ 회원가입이 성공적으로 완료되었습니다! 이제 로그인하여 학습을 시작하세요.</div>', unsafe_allow_html=True)
        st.session_state.signup_success = False

    col1, col2 = st.columns(2)
    with col1:
        with st.form("login_form"):
            st.header("로그인")
            username = st.text_input("사용자 이름", key="login_user")
            password = st.text_input("비밀번호", type="password", key="login_pass")
            if st.form_submit_button("로그인"):
                users = load_users()
                if username in users and users[username]["password"] == hash_password(password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.user_info = users[username]
                    st.rerun()
                else:
                    st.error("사용자 이름 또는 비밀번호가 잘못되었습니다.")
    with col2:
        with st.form("signup_form"):
            st.header("회원가입")
            new_username = st.text_input("새 사용자 이름", key="signup_user")
            new_password = st.text_input("새 비밀번호", type="password", key="signup_pass")
            if st.form_submit_button("회원가입"):
                users = load_users()
                if new_username in users:
                    st.error("이미 존재하는 사용자 이름입니다.")
                elif not new_username or not new_password:
                    st.warning("사용자 이름과 비밀번호를 모두 입력해주세요.")
                else:
                    users[new_username] = {
                        "password": hash_password(new_password),
                        "skill_test_taken": False, "language": None, "level": None,
                        "solved_problems": [], "total_score": 0
                    }
                    save_users(users)
                    st.session_state.signup_success = True
                    st.rerun()

def run_skill_test(language):
    st.header(f"'{language}' 기초 실력 테스트")

    if st.session_state.get('test_completed', False):
        st.success(f"테스트 완료! {st.session_state.total_questions}문제 중 {st.session_state.score}문제를 맞혔습니다. (정답률: {st.session_state.score_percent:.1f}%)")
        st.balloons()
        st.info(f"당신의 레벨은 '{st.session_state.user_info['level']}'로 측정되었습니다. 이제 맞춤형 문제를 풀어보세요!")

        if st.button("학습 시작하기"):
            for key in ['test_completed', 'score', 'total_questions', 'score_percent', 'start_test', 'test_language']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        return

    st.info("정확한 실력 측정을 위해 모든 문제에 신중하게 답변해주세요.")
    questions = problems_db["skill_test"].get(language, [])
    if not questions:
        st.error("죄송합니다. 현재 해당 언어의 실력 테스트 문제가 준비되지 않았습니다.")
        return

    with st.form("skill_test_form"):
        user_answers = [st.radio(q["question"], q["options"], key=f"q{i}") for i, q in enumerate(questions)]
        submitted = st.form_submit_button("결과 확인하기")

    if submitted:
        score = sum(1 for i, ua in enumerate(user_answers) if ua == questions[i]["answer"])
        total_questions = len(questions)
        score_percent = (score / total_questions) * 100 if total_questions > 0 else 0

        levels = list(problems_db["practice_problems"][language].keys())
        if score_percent >= 90: level = levels[4]
        elif score_percent >= 70: level = levels[3]
        elif score_percent >= 50: level = levels[2]
        elif score_percent >= 30: level = levels[1]
        else: level = levels[0]
        
        users = load_users()
        user = users[st.session_state["username"]]
        user.update({"skill_test_taken": True, "language": language, "level": level})
        save_users(users)

        st.session_state.user_info = user
        st.session_state.score = score
        st.session_state.total_questions = total_questions
        st.session_state.score_percent = score_percent
        st.session_state.test_completed = True
        st.rerun()

def show_dashboard():
    user_info = st.session_state.user_info
    
    # --- 사이드바 ---
    st.sidebar.header(f"🧑‍💻 {st.session_state.username}님")
    st.sidebar.metric("총 획득 점수", f"{user_info.get('total_score', 0)} 점")
    
    # --- 학습 설정 변경 기능 추가 ---
    st.sidebar.divider()
    st.sidebar.subheader("학습 설정")
    
    current_lang_index = ["Python", "C", "Java"].index(user_info['language'])
    new_lang = st.sidebar.selectbox(
        "학습 언어 변경",
        ["Python", "C", "Java"],
        index=current_lang_index
    )

    level_options = list(problems_db["practice_problems"][new_lang].keys())
    # 현재 레벨이 새 언어의 레벨 리스트에 없으면 첫번째 레벨로 설정
    try:
        current_level_index = level_options.index(user_info['level'])
    except ValueError:
        current_level_index = 0

    new_level = st.sidebar.selectbox(
        "난이도 변경",
        level_options,
        index=current_level_index
    )

    if st.sidebar.button("설정 저장", use_container_width=True):
        users = load_users()
        user = users[st.session_state.username]
        user['language'] = new_lang
        user['level'] = new_level
        save_users(users)
        st.session_state.user_info = user
        st.session_state.current_problem = None # 설정을 바꿨으니 현재 문제 초기화
        st.sidebar.success("설정이 저장되었습니다!")
        time.sleep(1)
        st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("로그아웃", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # --- 메인 대시보드 ---
    st.markdown(f'<p class="main-title">"{user_info["language"]}" 학습 대시보드</p>', unsafe_allow_html=True)
    st.info(f"현재 **{user_info['level']}** 레벨의 문제를 풀고 있습니다.")
    
    if st.button("새로운 문제 받기", type="primary", use_container_width=True):
        problem_pool = problems_db["practice_problems"][user_info['language']][user_info['level']]
        unsolved_problems = [p for p in problem_pool if p['id'] not in user_info.get('solved_problems', [])]
        if unsolved_problems:
            st.session_state.current_problem = random.choice(unsolved_problems)
        else:
            st.success("축하합니다! 현재 레벨의 모든 문제를 해결했습니다. 사이드바에서 다음 레벨에 도전해보세요!")
            st.session_state.current_problem = None
        st.rerun()

    if "current_problem" in st.session_state and st.session_state.current_problem:
        problem = st.session_state.current_problem
        st.markdown(f"""
            <div class="problem-card">
                <p class="points">{problem['points']} 점</p>
                <h3>{problem['title']}</h3>
                <p>{problem['description']}</p><hr>
                <b>입력 예시:</b><pre><code>{problem['example_input']}</code></pre>
                <b>출력 예시:</b><pre><code>{problem['example_output']}</code></pre>
            </div>
        """, unsafe_allow_html=True)
        
        with st.form(key=f"form_{problem['id']}"):
            st.subheader("코드 입력")
            user_code = st.text_area("여기에 코드를 작성하세요:", height=200, key=f"code_{problem['id']}", placeholder=f"{user_info['language']} 코드를 입력...")
            submit_button = st.form_submit_button("AI에게 채점받기")

        if submit_button:
            if not user_code.strip():
                st.warning("코드를 입력해주세요.")
            else:
                with st.spinner("AI가 코드를 채점 중입니다..."):
                    is_correct, feedback = asyncio.run(grade_with_ai_real(user_code, problem, user_info['language']))

                if is_correct:
                    st.success(f"채점 결과: {feedback}")
                    users = load_users()
                    user = users[st.session_state.username]
                    
                    # --- 오류 수정 부분 ---
                    # 이전 버전의 user 데이터에 solved_problems, total_score 키가 없을 경우를 대비
                    if 'solved_problems' not in user:
                        user['solved_problems'] = []
                    if 'total_score' not in user:
                        user['total_score'] = 0
                    # --- 오류 수정 끝 ---

                    if problem['id'] not in user['solved_problems']:
                        user['solved_problems'].append(problem['id'])
                        user['total_score'] += problem['points']
                        save_users(users)
                        st.session_state.user_info = user
                        st.balloons()
                        st.info(f"{problem['points']}점을 획득했습니다! 총 점수: {user['total_score']}점")
                        st.session_state.current_problem = None
                        time.sleep(3)
                        st.rerun()
                    else:
                        st.info("이미 해결한 문제입니다. 점수는 추가되지 않습니다.")
                else:
                    st.error(f"채점 결과: {feedback}")

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
