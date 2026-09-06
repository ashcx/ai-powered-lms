import streamlit as st
import os, requests, time, json, re, random
from datetime import datetime
from streamlit.components.v1 import html
from streamlit.components.v1 import html as components_html

from api.client import (
    get_student_subjects,
    get_student_subtopic_scores,
    get_correct_wrong_questions,
    enumerate_subtopics,
    stream_explain,
    chat_stream,
    classify_questions,
)

# UI Components
from components.charts import web_chart, plt_boxplot

import random
import streamlit as st
from api.client import get_correct_wrong_questions  # already in your project


def get_wrong_questions(student_id: str, module_id: str, subtopic: str=None):
    incorrect_questions = [
        q["question_text"]
        for q in get_correct_wrong_questions(student_id, module_id, subtopic)
        if not q["is_correct"]
    ]

    if incorrect_questions:
        return incorrect_questions
    else:
        st.write("No incorrectly answered questions.")
        return None


def flashcards_section(student_id: str, module_id: str, subtopics_list: list):
    """Render the flashcards UI inside the student module page."""

        # --- Custom font and button styles for flashcards ---
    st.markdown(
        '''
        <style>
        @font-face {
            font-family: 'Raleway ExtraBold';
            src: url('../Raleway-ExtraBold.ttf') format('truetype');
            font-weight: 800;
            font-style: normal;
        }
        .flip-card-front, .flip-card-back {
            font-family: 'Raleway ExtraBold', sans-serif !important;
            font-size: 1.5rem !important;
        }
        button[data-testid="stButton"] {
            background-color: #0073e6 !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 50% !important;
            width: 48px !important;
            height: 48px !important;
            font-size: 1.2rem !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0 !important;
        }
        button[data-testid="stButton"]:hover {
            background-color: #005bb5 !important;
        }
        </style>
        ''',
        unsafe_allow_html=True
    )

    unique_subtopics = [s['subtopic'] for s in subtopics_list]
    
    if "selected_subtopic" not in st.session_state or st.session_state["selected_subtopic"] not in unique_subtopics:
        st.session_state["selected_subtopic"] = unique_subtopics[0]

    if len(unique_subtopics) > 4:
        rows = [unique_subtopics[i:i+4] for i in range(0, len(unique_subtopics), 4)]
        for row in rows:
            cols = st.columns(4)
            for idx, subtopic in enumerate(row):
                if cols[idx].button(subtopic, key=f"subtopic_chip_{subtopic}"):
                    st.session_state["selected_subtopic"] = subtopic
    else:
        cols = st.columns(len(unique_subtopics))
        for idx, subtopic in enumerate(unique_subtopics):
            if cols[idx].button(subtopic, key=f"subtopic_chip_{subtopic}"):
                st.session_state["selected_subtopic"] = subtopic

    selected_subtopic = st.session_state["selected_subtopic"]
    st.markdown(f"Selected subtopic: **{selected_subtopic}**")

    # ---------- 1. Pull & cache the deck (per subtopic) ---------- #
    deck_key = f"deck_{student_id}_{module_id}_{selected_subtopic}"
    src_key  = f"deck_src_{student_id}_{module_id}_{selected_subtopic}"
    cards = st.session_state.get(deck_key, [])

    with st.spinner("Hold on! Flashcards are on their way!"):
        # Always fetch the latest list of wrong questions for this subtopic
        incorrect_questions = get_wrong_questions(
            student_id=student_id, module_id=module_id, subtopic=selected_subtopic
        )

        # Normalized signature of the source questions to detect changes
        src_sig = None
        if incorrect_questions:
            try:
                src_sig = json.dumps(incorrect_questions, ensure_ascii=False, sort_keys=True)
            except Exception:
                src_sig = "|".join(map(str, incorrect_questions))

        if not incorrect_questions:
            st.info("🎉 Great job – no wrong-question flashcards to review!")
            return

        # Only (re)generate if we don't have a deck yet or the source questions changed
        need_regen = (deck_key not in st.session_state) or (st.session_state.get(src_key) != src_sig)

        if need_regen:
            ## AI generation part
            flashcard_qns_key = f"flashcard_qns_{student_id}_{module_id}_{selected_subtopic}"
            prompt = (
                f"""
                You are an educational assistant AI. Output all data into a JSON object in the format stated below.
                The output data should be an array of questions YOU GENERATE, NOT the questions given to you as reference in WRONG_QUESTIONS_JSON.  
                The WRONG_QUESTIONS_JSON given to you below contains a list of questions a student got wrong 
                in a specific module (identified by {module_id}) and specific subtopic (identified by {selected_subtopic}). 
                Each item includes the original question text.

                WRONG_QUESTIONS_JSON = {json.dumps(incorrect_questions, ensure_ascii=False)}

                INSTRUCTIONS:
                Your task is to generate a JSON object of personalized flashcards to help the student revise key 
                concepts they appear to struggle with.

                1. Analyze the Mistakes:
                • Identify common topics, concepts, or subtopics the student is struggling with.

                2. Create Flashcards:
                • Each flashcard should be a short conceptual question.
                • Make sure the question is not directly copied from the student’s mistakes but is conceptually related.
                • The answer must be concise: one word or a few keywords only — no full sentences.
                • Use simple, clear language appropriate for quick revision.

                3. Format the output:
                • The output must be a JSON object with the following structure:
                '{{
                "flashcards": [
                    {{"question": "What is the primary key used for in a database?", "answer": "unique identifier"}},
                    {{"question": "What loop repeats a fixed number of times?", "answer": "for loop"}}
                ]
                }}'

                4. Flashcard Count:
                • Limit to 10-15 flashcards. 
                • Avoid redundancy; each flashcard should cover a unique concept.
                """.strip()
            )


            # Call AI (stream) and cache raw text in session by the streaming helper
            if flashcard_qns_key not in st.session_state:
                with st.spinner("Hold on! Flashcards are on their way!"):
                    # Consume the generator into a full string
                    resp_text = chat_stream(prompt, cache_key=flashcard_qns_key, stream=False)
                    st.session_state[flashcard_qns_key] = resp_text
            else:
                resp_text = st.session_state[flashcard_qns_key]

            # Parse JSON from response (handle dict or string; strip ```json fences)
            resp_obj = None
            if isinstance(resp_text, (dict, list)):
                # chat_stream may already return a parsed object
                resp_obj = resp_text
            elif isinstance(resp_text, str):
                s = resp_text.strip()
                # remove code fences if present
                if s.startswith("```"):
                    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.S).strip()
                # try direct parse
                try:
                    resp_obj = json.loads(s)
                except Exception:
                    # Fallback: extract first JSON object/array from the text
                    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", s)
                    if m:
                        resp_obj = json.loads(m.group(1))
                    else:
                        st.error("Could not parse flashcards JSON from AI response.")
                        print(resp_text)
                        return
            else:
                st.error("Unexpected response type from AI. Expected str or dict.")
                print(type(resp_text), resp_text)
                return

            cards = [
                {"q": row["question"], "a": row["answer"]}
                for row in resp_obj.get('flashcards', [])
                if isinstance(row, dict) and "question" in row and "answer" in row
            ]
            # Shuffle ONCE on generation
            random.shuffle(cards)
            st.session_state[deck_key] = cards
            st.session_state[src_key]  = src_sig
            # Reset navigation on regeneration
            st.session_state.fc_idx = 0 

            # Edge-case guard
            if not cards:
                st.info("🎉 Great job – no wrong-question flashcards to review!")
                return

    # ---------- 4. Flashcard UI (custom embed) ---------- #
    cards_json = json.dumps(cards)
    html_content = f"""
<link href="https://fonts.googleapis.com/css2?family=Raleway:wght@800&display=swap" rel="stylesheet">
<style>
  .flashcard-wrapper {{ display:flex; flex-direction:column; align-items:center; }}
  .flip-card {{ width: 400px; height: 250px; perspective: 1000px; }}
  .flip-card-inner {{ position: relative; width: 100%; height: 100%; text-align: center;
                     transition: transform 0.6s; transform-style: preserve-3d;
                     font-family: 'Raleway', sans-serif; font-size: 1.5rem; cursor: pointer; }}
  .flip-card.flipped .flip-card-inner {{ transform: rotateY(180deg); }}
  .flip-card-front, .flip-card-back {{ position: absolute; width: 92%; height: 100%;
                                     backface-visibility: hidden; border-radius: 10px;
                                     display: flex; align-items: center; justify-content: center; padding: 1rem; }}
  .flip-card-front {{ background: #1e1e1e; color: #f5f5f5; }}
  .flip-card-back {{ background: #333; color: #8ab4f8; transform: rotateY(180deg); }}
  .nav-buttons {{ margin-top: 3rem; display: flex; gap: 1rem; }}
  .nav-buttons button {{ background: #0073e6; border: none; color: white;
                        border-radius: 50%; width: 48px; height: 48px;
                        font-size: 1.5rem; cursor: pointer; }}
  .nav-buttons button:disabled {{ opacity: 0.5; cursor: default; }}
</style>
<div class="flashcard-wrapper">
  <div id="flashcard" class="flip-card">
    <div class="flip-card-inner" id="flipInner">
      <div class="flip-card-front" id="cardFront"></div>
      <div class="flip-card-back" id="cardBack"></div>
    </div>
  </div>
  <div class="nav-buttons">
    <button id="prevBtn">◀</button>
    <button id="nextBtn">▶</button>
  </div>
  <div style="margin-top:0.5rem; color: grey;" id="counter"></div>
</div>
<script>
  const cards = {cards_json};
  let idx = 0;
  const front = document.getElementById('cardFront');
  const back = document.getElementById('cardBack');
  const flipInner = document.getElementById('flipInner');
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  function renderCard() {{
    front.textContent = cards[idx].q;
    back.textContent = cards[idx].a;
    const container = document.getElementById('flashcard');
    container.classList.remove('flipped');
    counter.textContent = `${{idx+1}} / ${{cards.length}}`;
    prevBtn.disabled = idx === 0;
    nextBtn.disabled = idx === cards.length - 1;
  }}
  prevBtn.addEventListener('click', () => {{ idx--; renderCard(); }});
  nextBtn.addEventListener('click', () => {{ idx++; renderCard(); }});
  flipInner.parentElement.addEventListener('click', () => {{
    flipInner.parentElement.classList.toggle('flipped');
  }});
  const counter = document.getElementById('counter');
  counter.style.fontFamily = 'Raleway ExtraBold, sans-serif';
  renderCard();
</script>
"""
    components_html(html_content, height=400)

    with st.expander("📋 Quick reference – all flashcards"):
        for i, c in enumerate(cards, 1):
            st.markdown(
                f"""
                <div style='background:#111;padding:0.8rem 1rem;margin-bottom:0.4rem;
                            border-radius:6px;font-size:0.9rem;'>
                    <b>{i}. {c['q']}</b><br>
                    <span style='color:#8ab4f8;'>{c['a']}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("How flashcards works"):
        st.markdown(
            """
            These flashcards are auto-generated from the questions you answered
            incorrectly. Click the card to flip between question and answer.
            Use the arrows to move between cards.
            """
        )