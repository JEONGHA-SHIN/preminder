#app.py
import streamlit as st
import requests

BASE_URL = "http://localhost:8000"

# def login():
#     st.title("Preminder Login")
#     email = st.text_input("Enter your email")
#     if st.button("Login"):
#         try:
#             response = requests.post(f"{BASE_URL}/users/", json={"email": email})
#             response.raise_for_status()
#             st.session_state.user_email = email
#             st.session_state.messages = []
#             st.success("Logged in successfully!")
#             st.rerun()
#         except requests.RequestException as e:
#             st.error(f"Login failed: {str(e)}")
def login():
    st.title("Preminder Login")
    
    with st.form("login_form"):
        email = st.text_input("Enter your email")
        submitted = st.form_submit_button("Login")

    if submitted or (email and st.session_state.get('login_attempt', False)):
        try:
            response = requests.post(f"{BASE_URL}/users/", json={"email": email})
            response.raise_for_status()
            st.session_state.user_email = email
            st.session_state.messages = []
            st.success("Logged in successfully!")
            st.rerun()
        except requests.RequestException as e:
            st.error(f"Login failed: {str(e)}")
    
    # 폼이 제출되지 않았지만 이메일이 입력된 경우, 다음 실행에서 로그인 시도
    if email and not submitted:
        st.session_state.login_attempt = True
    else:
        st.session_state.login_attempt = False
                        
def chat_with_gemini():
    st.header("Chat with Gemini to Create Your Event Query")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What event would you like to track?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response = requests.post(f"{BASE_URL}/chat_with_gemini/", json={"message": prompt, "user_email": st.session_state.user_email})
            assistant_response = response.json()["response"]
            st.markdown(assistant_response)
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Finalize Search Query"):
            response = requests.post(f"{BASE_URL}/finalize_search_query/", json={"user_email": st.session_state.user_email})
            final_query = response.json()["final_query"]
            st.session_state.final_query = final_query
            st.success(f"Suggested search query: {final_query}")
    
    with col1:
        if "final_query" in st.session_state and st.button("Confirm Search Query"):
            response = requests.post(f"{BASE_URL}/confirm_search_query/", json={"user_email": st.session_state.user_email, "final_query": st.session_state.final_query})
            st.success("Search query confirmed and saved!")
            st.session_state.messages = []  # 채팅 히스토리 초기화
            st.session_state.pop("final_query", None)  # final_query 제거
            st.rerun()
            
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
    st.title("Preminder")
    st.write(f"Welcome, {st.session_state.user_email}!")
    
    chat_with_gemini()
    
    if st.checkbox("Show Test Interface"):
        test_search_interface()
    
    # Sidebar with event list
    st.sidebar.title("Your Events")
    try:
        response = requests.get(f"{BASE_URL}/events/{st.session_state.user_email}")
        response.raise_for_status()
        events = response.json()
        for event in events:
            col1, col2 = st.sidebar.columns([4, 1])
            col1.write(event['search_query'])
            if col2.button("🗑️", key=f"delete_{event['id']}", help="Delete this event"):
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