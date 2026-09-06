import requests, re, json
import os
import streamlit as st

API_BASE = os.getenv("FAST_API_URL", "http://localhost:8000")

def chat_stream(prompt: str, model = '5-chat', cache_key: str | None = None, stream: bool = True):
    # automatically chooses model based on model type
    # three types of models -- normal, mini, and nano
    # this can be changed and customised easily to fit user needs
    if model == 'normal':
        model = 'gpt-4.1-2025-04-14'
    elif model == 'mini':
        model = 'gpt-4.1-mini-2025-04-14'
    elif model == 'nano':
        model = 'gpt-4.1-nano-2025-04-14'
    elif model == '5-chat':
        model = 'gpt-5-chat-latest'
    elif model == '5-mini':
        model = 'gpt-5-mini'
    elif model == '5-nano':
        model = 'gpt-5-nano'
    else:
        model = 'gpt-4.1-mini-2025-04-14'

    if model[:5] == 'gpt-5':
        prompt += "\nRespond as quickly as possible. DO NOT SPEND TIME REASONING. DO NOT THINK HARD."
        prompt += "\nDO NOT END YOUR RESPONSE WITH ANY FORM OF SUGGESTIONS, LIKE 'Do you want me to also do X?' NEVER END YOUR RESPONSE WITH ANY FORM OF SUGGESTIONS."

    # Always stream first, then cache
    full = ""
    resp = requests.post(f"{API_BASE}/chat", params={"model": model, "stream": str(stream).lower()}, json={"query": prompt}, stream=stream)

    if stream:
        # NESTED generator so the outer function is NOT a generator
        def _gen():
            nonlocal full
            for chunk in resp.iter_content(decode_unicode=True):
                if not chunk:
                    continue
                full += chunk
                yield chunk
            # cache after completion
            if cache_key:
                try:
                    import streamlit as st
                    st.session_state[cache_key] = full
                except Exception:
                    pass
        return _gen()  # <- returns a generator ONLY when streaming
    
    # non streaming
    text = resp.text.strip()
    try:
        if "```json" in text[:10] or "json" in text[:10]:
            text = text.replace("json", '')
            text = text.replace("```", '')
            return json.loads(text)
        else:
            return text
    except Exception as e:
        print(text)

    # after finish streaming, then store the full text
    if cache_key:
        st.session_state[cache_key] = full


def _replay_chunks(text: str, size: int = 100):
    """Yield text in fixed-size chunks (used when replaying from cache)."""
    for i in range(0, len(text), size):
        yield text[i:i+size]


# mostly student functions 
@st.cache_resource
def enumerate_subtopics(module_id: str) -> list[str]:
    return requests.get(f"{API_BASE}/enumerate_subtopics/{module_id}").json() or []

@st.cache_resource
def get_student_subjects(student_id: str):
    return requests.get(f"{API_BASE}/subjects/{student_id}").json() or []

@st.cache_resource
def get_student_subtopic_scores(student_id: str, module_id: str):
    return requests.get(f"{API_BASE}/subtopics/{student_id}/{module_id}").json() or []

@st.cache_resource
def get_correct_wrong_questions(student_id: str, module_id: str, subtopic: str):
    return requests.get(f"{API_BASE}/correct_wrong_questions/{student_id}/{module_id}/{subtopic}").json() or []


def stream_explain(module_id: str, query: str, k: int = 4, cache_key: str | None = None):
    """
    Yield an explanation from /stream-explain chunk by chunk.
    If cache_key is provided, replay cached text on subsequent calls.
    """
    # Replay straight from cache?
    if cache_key and cache_key in st.session_state:
        yield from _replay_chunks(st.session_state[cache_key])
        return

    # Live stream from API
    full = ""
    resp = requests.post(
        f"{API_BASE}/stream-explain",
        json={"module_id": module_id, "query": query, "k": k},
        stream=True,
    )
    # decode_unicode=True => each chunk is already str
    for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
        full += chunk
        yield chunk

    if cache_key:
        st.session_state[cache_key] = full
 

# mostly teacher functions
@st.cache_resource
def get_teacher_subjects():
    return requests.get(f"{API_BASE}/all_subjects").json() or []

@st.cache_data(show_spinner=False, ttl=3600)
def classify_questions(prompt: str) -> dict:
    """Classify numbered questions into difficulty categories."""
    resp_text = "".join(chunk for chunk in chat_stream(prompt, model='nano'))
    # Try to extract the first JSON object from the response
    match = re.search(r'\{[\s\S]*\}', resp_text)
    json_text = match.group(0) if match else resp_text
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return {}

@st.cache_resource
def get_top_students(n: int = 10) -> list[dict]:
    """
    GET /top_10  →  [{ student_id, score }, …]
    """
    return requests.get(f"{API_BASE}/get_top_students").json() or []

@st.cache_resource
def get_last_students(n: int = 10) -> list[dict]:
    """
    GET /last_10  →  [{ student_id, score }, …]
    """
    return requests.get(f"{API_BASE}/get_last_students").json() or []

@st.cache_resource
def avg_subtopic_scores(module_id: str) -> dict:
    """
    GET /avg_subtopic_scores/{module_id}
    →  { subtopic, avg_score }
    """
    return requests.get(
        f"{API_BASE}/avg_subtopic_scores/{module_id}"
    ).json() or {}

@st.cache_resource
def overall_summary() -> dict:
    """
    GET /overall_summary
    →  { module_id, summary }
    """
    return requests.get(f"{API_BASE}/overall_summary").json() or {}

@st.cache_resource
def module_wrong_questions(module_id: str) -> dict:
    """
    GET /module_wrong_questions/{module_id}
    →  { subtopic, avg_score }
    """
    return requests.get(
        f"{API_BASE}/module_wrong_questions/{module_id}"
    ).json() or {}

@st.cache_resource
def get_documents(module_id: str) -> dict:
    """
    GET /get_documents/{module_id}
    →  { subtopic, avg_score }
    """
    return requests.get(
        f"{API_BASE}/get_documents/{module_id}"
    ).json() or {}