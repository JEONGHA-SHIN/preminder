#app.py
import streamlit as st
import requests

BASE_URL = "http://localhost:8000"

st.set_page_config(
    page_title="PREMINDER",
    page_icon="⏳",  # 여기에 원하는 이모지나 아이콘 파일 경로를 지정할 수 있습니다
    layout="wide"  # 옵션: "centered" 또는 "wide"
)

def login():
    st.title("⏳ PREMINDER")
    st.markdown("<h3 style='font-size: 18px;'>중요한 일정을 놓치지 마세요😔 - 프리마인더가 먼저 찾아 알림을 제공합니다😼</h3>", unsafe_allow_html=True)

    
    with st.form("login_form"):
        email = st.text_input("📮 이메일로 시작하기")
        submitted = st.form_submit_button("Login")

    if submitted or (email and st.session_state.get('login_attempt', False)):
        try: 
            response = requests.post(f"{BASE_URL}/users/", json={"email": email})
            response.raise_for_status()
            st.session_state.user_email = email
            st.session_state.messages = []
            st.success("로그인 성공!😀")
            st.rerun()
        except requests.RequestException as e:
            st.error(f"로그인 실패😭: {str(e)}")
    
    # 폼이 제출되지 않았지만 이메일이 입력된 경우, 다음 실행에서 로그인 시도
    if email and not submitted:
        st.session_state.login_attempt = True
    else:
        st.session_state.login_attempt = False
                        
def chat_with_gemini():
    st.header("일정을 찾기위한 검색어를 도출해요")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "chat_started" not in st.session_state:
        st.session_state.chat_started = False
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("예. 2025 BTS 티케팅 접수 시작일을 알고싶어"):
        st.session_state.chat_started = True  # 채팅 시작 표시
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response = requests.post(f"{BASE_URL}/chat_with_gemini/", json={"message": prompt, "user_email": st.session_state.user_email})
            assistant_response = response.json()["response"]
            st.markdown(assistant_response)
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})
    
    if st.session_state.chat_started:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("이쯤에서 검색어 도출하기"):
                response = requests.post(f"{BASE_URL}/finalize_search_query/", json={"user_email": st.session_state.user_email})
                final_query = response.json()["final_query"]
                st.session_state.final_query = final_query
                st.success(f"Suggested search query: {final_query}")
        
        with col1:
            if "final_query" in st.session_state and st.button("검색어 확정하기"):
                response = requests.post(f"{BASE_URL}/confirm_search_query/", json={"user_email": st.session_state.user_email, "final_query": st.session_state.final_query})
                st.success("일정을 찾기위한 검색어가 확정되었습니다!")
                st.session_state.messages = []  # 채팅 히스토리 초기화
                st.session_state.pop("final_query", None)  # final_query 제거
                st.session_state.chat_started = False  # 채팅 시작 상태 초기화
                st.rerun()
    
    
    # col1, col2 = st.columns(2)
    # with col1:
    #     if st.button("이쯤에서 검색어 도출하기"):
    #         response = requests.post(f"{BASE_URL}/finalize_search_query/", json={"user_email": st.session_state.user_email})
    #         final_query = response.json()["final_query"]
    #         st.session_state.final_query = final_query
    #         st.success(f"Suggested search query: {final_query}")
    
    # with col1:
    #     if "final_query" in st.session_state and st.button("검색어 확정하기"):
    #         response = requests.post(f"{BASE_URL}/confirm_search_query/", json={"user_email": st.session_state.user_email, "final_query": st.session_state.final_query})
    #         st.success("일정을 찾기위한 검색어가 확정되었습니다!")
    #         st.session_state.messages = []  # 채팅 히스토리 초기화
    #         st.session_state.pop("final_query", None)  # final_query 제거
    #         st.rerun()
            
def test_search_interface():
    st.header("Test Search and Relevance")
    query = st.text_input("Enter a search query")
    if st.button("Test Search"):
        response = requests.post(f"{BASE_URL}/test_search/", json={"query": query})
        data = response.json()
        
        st.subheader("Summary")
        st.json(data["summary"])
        
        st.subheader("Detailed Results")
        for result in data["results"]:
            st.write(f"Title: {result['title']}")
            st.write(f"Snippet: {result['snippet']}")
            st.write(f"Link: {result['link']}")
            st.write(f"Topic Relevant: {'Yes' if result['topic_relevant'] else 'No'}")
            st.write(f"Contains Future Date: {'Yes' if result['future_date'] else 'No'}")
            st.write("---")

            
def main_app():
    st.title("⏳ PREMINDER")
    st.write(f"환영합니다, {st.session_state.user_email}!")
    
    chat_with_gemini()
    
    if st.checkbox("Show Test Interface"):
        test_search_interface()
    
    # Sidebar with event list
    st.sidebar.title("🔎 등록된 검색어")
    try:
        response = requests.get(f"{BASE_URL}/events/{st.session_state.user_email}")
        response.raise_for_status()
        events = response.json()
        for event in events:
            col1, col2 = st.sidebar.columns([4, 1])
            col1.write(event['search_query'])
            if col2.button("❌", key=f"delete_{event['id']}", help="Delete this event"):
                try:
                    delete_response = requests.delete(f"{BASE_URL}/events/{event['id']}")
                    delete_response.raise_for_status()
                    st.sidebar.success(f"Event {event['id']} deleted")
                    st.rerun()
                except requests.RequestException as e:
                    st.sidebar.error(f"Failed to delete event: {str(e)}")
    except requests.RequestException as e:
        st.sidebar.error(f"Failed to load events: {str(e)}")
    
    # # Main chat interface
    # st.header("Chat with Preminder")

    # # Initialize chat history
    # if "messages" not in st.session_state:
    #     st.session_state.messages = []

    # # Display chat messages from history on app rerun
    # for message in st.session_state.messages:
    #     with st.chat_message(message["role"]):
    #         st.markdown(message["content"])

    # # React to user input
    # if prompt := st.chat_input("What event would you like to track?"):
    #     # Display user message in chat message container
    #     st.chat_message("user").markdown(prompt)
    #     # Add user message to chat history
    #     st.session_state.messages.append({"role": "user", "content": prompt})

    #     try:
    #         response = requests.post(f"{BASE_URL}/events/", json={"user_email": st.session_state.user_email, "event_description": prompt})
    #         response.raise_for_status()
    #         event = response.json()
    #         response = f"I've registered your event: {prompt}. The optimal search query for this event is: '{event['search_query']}'. Is there anything else you'd like to add?"
    #     except requests.RequestException as e:
    #         response = f"Failed to register event: {str(e)}"

    #     # Display assistant response in chat message container
    #     with st.chat_message("assistant"):
    #         st.markdown(response)
    #     # Add assistant response to chat history
    #     st.session_state.messages.append({"role": "assistant", "content": response})

def logout():
    if st.sidebar.button("Logout"):
        del st.session_state.user_email
        del st.session_state.messages
        st.rerun()

if __name__ == "__main__":
    if 'user_email' not in st.session_state:
        login()
    else:
        logout()
        main_app()