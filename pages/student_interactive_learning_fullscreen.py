import streamlit as st
import os, tempfile, uuid, argparse, openai, re, shlex, json, platform, subprocess, sys, shutil
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm
from streamlit.components.v1 import html
from pathlib import Path
from typing import Optional

from api.client import (
    get_student_subjects,
    get_student_subtopic_scores,
    get_correct_wrong_questions,
    enumerate_subtopics,
    stream_explain,
    chat_stream,
    classify_questions,
    get_documents
)

# UI Components
from components.charts import web_chart, plt_boxplot
from components import movie as mtc


load_dotenv()
API_BASE = os.getenv("FAST_API_URL", "http://localhost:8000")  # FastAPI origin

# Load global CSS styles from file
with open('global_styles.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

st.markdown(f'''
    <style>
        .stMainBlockContainer.block-container {{
            padding-top: 0.5rem !important;
            max-width: 1400px !important;
        }}
        /* Target Streamlit columns */
        [data-testid="column"] > div {{
            width: 50vw !important;
            max-width: 700px !important;
        }}
        .stColumn{{
            width: calc(50% - 1rem) !important;
            flex: unset !important; 
        }}
        .stMarkdown p, .stMarkdown li{{
            font-size: 0.85rem !important;
        }}

        .stChatMessage{{
            padding: 0.5rem 0rem 0.5rem 1rem !important;
        }}
    </style>''', unsafe_allow_html=True)

## functions
def generate_script_and_outline(subtopic: str, mode: str, student_id: Optional[str] = None, module_id: Optional[str] = None):
    """Generate a script and bullet objectives based on the selected mode."""
    if mode == "Learn Fresh":
        documents = get_documents(module_id)
        prompt = f'''You’re writing a short, TikTok-style explainer video script (1–3 minutes) on the topic: “{subtopic}.” 

        Audience: a curious student who’s never seen this before. 

        Tone: friendly, upbeat, and conversational—think “talking to a friend.” 

        Outline:
        {documents}

        Structure:
        1. Hook: one sentence that grabs attention (one example is “Ever wondered how X works?”, but it's not necessary to follow).
        2. Core Concepts: 3–4 short but SPECIFIC points (2–3 sec each) that define or illustrate {subtopic}.
        3. Real-World Example: one relatable scenario.
        4. Wrap-Up: one quick sentence that ties it all together and teases next steps.

        Requirements:
        • Sentences no longer than 12 words.  
        • Use simple everyday language—no jargon.   
        • Include 3-4 bullet-style learning objectives (one phrase each).  
        • Total script length = MUST BE 250-350 WORDS LONG. 
        • The documents above contain all the class learning materials. You may pick those relevant to the subtopic at hand. 
        Please use the materials to help you generate the script.
        
        Output a JSON object:
        {{
        "script": "<your full video script here>",
        "objectives": ["Objective 1", "Objective 2", "Objective 3"]
        }}'''

    elif mode == "Revision":
        # Revision based on quiz mistakes
        documents = get_documents(module_id)
        prompt = f'''You’re writing a TikTok-style review video script (1–3 minutes) to help a student revise for a quiz on “{subtopic}.”

        Audience: a student who’s already learned the basics but needs a quick refresher.  

        Tone: energetic, encouraging—like a coach cheering you on.  

        Outline:
        {documents}

        Structure:
        1. Quick Reminder: one sentence recapping the core idea of {subtopic}. Go through the main points. 
        2. Common Pitfalls: 2–3 short but SPECIFIC points of mistakes students make.  
        3. Mini Practice: one rapid-fire question (example: “What does X mean?”).  
        4. Call to Action: (example: “Start revising today and you'll find out X / you'll ace your quiz”  

        Requirements:
        • Keep each line ≤ 12 words.  
        • Use direct, active verbs.  
        • Create 3 bullet learning objectives (e.g. “Recall the definition of X”).  
         • Total script length = MUST BE 400-500 WORDS LONG. 
        • The documents above contain all the class learning materials. You may pick those relevant to the subtopic at hand. 
        Please use the materials to help you generate the script.

        Output a JSON object:
        {{
        "script": "<your full video script here>",
        "objectives": ["Revision point 1", "Revision point 2", "Revision point 3"]
        }}'''

    elif mode == "Explain Mistakes":
        # Pull the student's wrong questions and explain
        # Assume get_correct_wrong_questions returns a list of dicts
        wrong_qs = [
                q["question_text"]
                for q in get_correct_wrong_questions(student_id, module_id, subtopic)
                if not q["is_correct"]
            ]
        
        prompt = f'''
        You’re writing a TikTok-style “error walkthrough” video script (1–3 minutes) about a student’s past mistakes in “{subtopic}.”

        Audience: a student who got specific quiz questions wrong.  

        Tone: empathetic and clear—like a friendly tutor guiding you.  

        Inputs:
        – A list of wrong questions and their correct answers:
        {wrong_qs}

        Structure:
        1. Empathy Hook: one sentence acknowledging “We all slip up.”  
        2. Pick three pertinent mistakes from the list.
        3. For each mistake:
        a. State the question in 1 short phrase.  
        b. Explain the correct concept concisely, then confirm the correct answer.   
        4. Takeaway Tips: 2-3 bullet-style tips to avoid the mistakes in similar questions. 

        Requirements:
        • Ultra-concise: sentences ≤ 12 words.  
        • Use “you” and “we” for connection.  
        • Provide 2–3 bullet learning objectives summarizing the fixes.  
        • Total script ≤ 2 minutes.  Around 200-300 words.
 
        Output a JSON object:
        {{
        "script": "<your full video script here>",
        "objectives": ["Tip 1", "Tip 2", "Tip 3"]
        }}'''

    print(prompt)
    resp_text = chat_stream(prompt, model='mini', stream=False)

    print(resp_text, "resp_text")

    # CHECK string or generator first
    if isinstance(resp_text, str):
        resp_text = resp_text
    else:
        resp_text = "".join(resp_text)

    try:
        response = json.loads(resp_text)
    except json.JSONDecodeError:
        st.error("Failed to parse JSON response from OpenAI.")
        print(resp_text)
        return None, None
    
    script_text = response.get("script", "")
    bullets = response.get("objectives", [])
    
    return script_text, bullets


def create_brainrot_video(script_text: str):
    """Send script to TTS + video generative pipeline and return local .mp4 path."""
    export_dir = Path(__file__).parent.resolve().parent / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    out_path = export_dir / f"brainrot_{uuid.uuid4().hex}.mp4"

    if mtc is not None:
        mtc.create_brainrot_video(text=script_text, output_path=out_path)
    else:
        return None
    return str(out_path)


def pill_css():
    st.markdown(
        """
        <style>
        .pill-container button {
            border: none;
            padding: 0.4rem 1rem;
            margin: 0.2rem;
            border-radius: 999px;
            background: #3a3f44;
            color: #f5f5f5;
            cursor: pointer;
            transition: background 0.2s;
        }
        .pill-container button.selected {
            background: #0073e6;
        }
        .pill-container button:hover {
            background: #005bb5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def pill_row(label: str, options: list[str], key_prefix: str):
    st.markdown(f"**{label}**")
    pill_css()

    # Always build at least one disabled placeholder column
    n_cols = max(len(options), 1)
    cols   = st.columns(n_cols)

    selected = st.session_state.get(f"{key_prefix}_selected")

    if options:
        # real options – render buttons
        for i, opt in enumerate(options):
            is_sel = (opt == selected)
            if cols[i].button(
                opt,
                key=f"{key_prefix}_{opt}",
                type="primary" if is_sel else "secondary",
                use_container_width=True,
            ):
                st.session_state[f"{key_prefix}_selected"] = opt
                st.session_state[f"{key_prefix}_clicked"]  = True
                selected = opt
    else:
        # no options yet – show a disabled placeholder so layout doesn’t change
        cols[0].button("…", key=f"{key_prefix}_placeholder", disabled=True, use_container_width=True)

    return selected

def fullscreen_section(student_id: str, module_id: str, subtopics_list: list = []):
    """Render the Interactive Learning UI in fullscreen."""
    # Back to inline view
    if st.button(f"← Back to {module_id} Insights", use_container_width=False):
        st.switch_page("app.py")
        st.session_state.stage == "student_module"
        st.stop()

    # Ensure chat history list exists
    if "brainrot_chat" not in st.session_state:
        st.session_state.brainrot_chat = []

    # Ensure storage for scripts and chat history exists
    if "video_scripts" not in st.session_state:
        st.session_state.video_scripts = []
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # ─── Retrieve identifiers pushed from gateway ────────────────────────
    student_id  = st.session_state.get("_il_student_id")
    module_id   = st.session_state.get("_il_module_id")
    subtopics_list = st.session_state.get("_il_subtopics")

    st.subheader(f"{module_id}: Interactive Learning (beta)")

    # ────────────────────────── Layout ──────────────────────────
    col_sel, col_chat = st.columns([1, 2])  # 1/3 and 2/3 widths

    with col_sel:
        # Pre-select first mode to avoid inserting new keys on first click
        default_modes = ["Learn Fresh", "Revision", "Explain Mistakes"]
        if st.session_state.get("mode_selected") is None:
            st.session_state["mode_selected"] = default_modes[0]
            st.session_state["mode_clicked"] = True

        # Mode & subtopic selection
        modes = default_modes
        mode = pill_row("What's on your mind?", modes, "mode")

        flat_subtopics = [s["subtopic"] for s in subtopics_list]
        subtopic = pill_row("Choose the subtopic:", flat_subtopics, "subtopic")

        # Generate button
        if st.session_state.get("mode_clicked") and st.session_state.get("subtopic_clicked"):
            if st.button("🎬 Generate Video", type="primary", use_container_width=True):
                with st.spinner("Writing text for your video..."):
                    script_text, bullets = generate_script_and_outline(subtopic, mode, student_id, module_id)
                # Store the full script for later review
                st.session_state.video_scripts.append({
                    "mode": mode,
                    "subtopic": subtopic,
                    "script": script_text,
                    "objectives": bullets,
                    "timestamp": datetime.now().isoformat(),
                })
                st.session_state.brainrot_chat.append({
                    "role": "assistant",
                    "content": "Let us cook... We'll be quick!",
                    "id": uuid.uuid4().hex
                })
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": "Let us cook... We'll be quick!",
                    "timestamp": datetime.now().isoformat()
                })
                st.session_state.brainrot_bullets = bullets
                with st.spinner("Creating video… Give us 30 seconds!"):
                    video_path = create_brainrot_video(script_text)
                st.session_state.brainrot_chat.append({
                    "role": "assistant",
                    "content": "Here’s your revision video!",
                    "video": video_path,
                    "script": script_text,        # <‑‑ include full script so it flows into context
                    "id": uuid.uuid4().hex
                })
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": "Here’s your revision video!",
                    "timestamp": datetime.now().isoformat()
                })
                # ── NEW FEATURE: create a quick summary and send automatically ──
                try:
                    summary_prompt = (
                        "Summarize the following video script.  "
                        "Use bulleted points where possible and only highlight the main points."
                        "3-5 bulleted points. "
                        "Use simple everyday language—no jargon. Write concisely. \n\n"
                        f"---\n{script_text}\n---"
                    )
                    collected = ""
                    placeholder = col_chat.empty()
                    for chunk in chat_stream(summary_prompt):
                        collected += chunk
                        placeholder.markdown(collected)
                    summary_text = collected

                    # Fallback if the model returns JSON/markdown – keep raw text
                    if summary_text.startswith("{"):
                        # attempt to load json with 'summary' key
                        try:
                            summary_text = json.loads(summary_text).get("summary", summary_text)
                        except Exception:
                            pass

                    # Append summary text to chat so user gets it immediately
                    st.session_state.brainrot_chat.append({
                        "role": "assistant",
                        "content": summary_text,
                        "script": summary_text,
                        "id": uuid.uuid4().hex
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": summary_text,
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    # Log but don't break the UX if summary fails
                    print("Summary generation failed:", e)

    with col_chat:
        # Chat rendering
        for msg in st.session_state.brainrot_chat:
            with st.chat_message(msg["role"]):
                if msg.get("video"):
                    # Show video with a max width of 400px
                    st.video(msg["video"], format="video/mp4", width=400)
                st.markdown(msg["content"])

        # User follow-up
        if user_query := st.chat_input("Ask a follow-up question…", key="il_chat_input"):
            st.session_state.brainrot_chat.append({"role": "user", "content": user_query, "id": uuid.uuid4().hex})
            # Build an augmented prompt that contains the last 8 turns
            hist_snips = []
            for m in st.session_state.brainrot_chat[-8:]:
                snippet = f"{m['role']}: {m['content']}"
                if m.get("script"):            # include video scripts if present
                    snippet += f"\n\n{m['script']}"
                hist_snips.append(snippet)
            context_block   = "\n".join(hist_snips)
            # --- Ensure the *full* video script is always included -----------------
            latest_script_block = None
            for m in reversed(st.session_state.brainrot_chat):
                if m.get("script"):
                    latest_script_block = m["script"]
                    break

            if latest_script_block:
                # Prepend the most recent script so the assistant can reference it,
                # even if that message falls outside the last‑8 window.
                context_block = f"""assistant (video script):\n{latest_script_block}\n\n{context_block}"""
            augmented_query = f"""{context_block}\n\nuser: {user_query}"""
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_query,
                "timestamp": datetime.now().isoformat()
            })
            with st.spinner("AI is typing…"):
                collected = ""
                placeholder = st.empty()
                for chunk in chat_stream(augmented_query):
                    collected += chunk
                    placeholder.markdown(collected)
                full_resp = collected
            st.session_state.brainrot_chat.append({"role": "assistant", "content": full_resp, "id": uuid.uuid4().hex})
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": full_resp,
                "timestamp": datetime.now().isoformat()
            })
            # Force immediate rerender so latest message appears
            st.rerun()

# ──────────────────────────────────────────────────────────────────
# Invoke fullscreen_section on page load
# ──────────────────────────────────────────────────────────────────
fullscreen_section(
    st.session_state.get("_il_student_id"),
    st.session_state.get("_il_module_id"),
    st.session_state.get("_il_subtopics"),
)
