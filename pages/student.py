import streamlit as st
import os, requests, time, json, re, random
from datetime import datetime
from streamlit.components.v1 import html

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
from pages.student_insights import insights_section
from pages.student_flashcards import flashcards_section
from pages.student_interactive_learning import interactive_learning_section

def student_dashboard(student_id: str):
    # Load button CSS styles from file
    with open('button_styles.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

    # Time-based greeting
    morning_greetings = ["Rise and shine", "Good morning", "Time to seize the day", "Ready to tackle today"]
    afternoon_greetings = ["Good afternoon", "Hope your day's going well", "Afternoon check-in", "Ready for more learning"]
    evening_greetings = ["Good evening", "Winding down the day", "Evening study session", "Time for some learning"]
    night_greetings = ["You're a night owl", "Burning the midnight oil", "Late night learner", "Still going strong"]

    current_hour = datetime.now().hour
    if 5 <= current_hour < 12:
        greeting = random.choice(morning_greetings)
    elif 12 <= current_hour < 18:
        greeting = random.choice(afternoon_greetings)
    elif 18 <= current_hour < 22:
        greeting = random.choice(evening_greetings)
    else:
        greeting = random.choice(night_greetings)

    st.header(f"🎓 {greeting}, {student_id}!")

    modules = get_student_subjects(student_id)
    if not modules:
        st.info("No modules found for this student.")
        return

    # Synchronous welcome message
    welcome_prompt = (
        "You are writing an encouraging welcome message for a student. "
        "Based on their grades, provide a personalized message to motivate them to continue learning. "
        "Write concisely and in an informal but not too casual tone. "
        + str(modules)
    )
    welcome_key = f"welcome_{student_id}"
    if welcome_key not in st.session_state:
        with st.spinner("Exploring your academic performance... Please wait"):
            # use gpt 4.1 mini for faster time to first token
            st.write_stream(chat_stream(welcome_prompt, model='mini', cache_key=welcome_key))
    else:
        st.write(st.session_state[welcome_key])

    st.subheader("Your Grades")
    web_chart([row['module_id'] for row in modules], [row['weighted_score'] for row in modules],
              sort='descending', unit='%')

    st.subheader("Your Subjects")
    st.write("Click a subject to explore and have fun learning!")
    cols = st.columns(3)
    for idx, mod in enumerate(modules):
        with cols[idx % 3]:
            if st.button(mod["module_id"], key=f"module_{mod['module_id']}"):
                st.session_state.selected_module = mod["module_id"]
                st.session_state.stage = "student_module"


def student_module_page(student_id: str, module_id: str):
    st.button("← Back", on_click=lambda: st.session_state.update({"stage": "student_dashboard"}))
    st.header(f"📘 {module_id}")

    subtopics_list = enumerate_subtopics(module_id)
    tab1, tab2, tab3 = st.tabs(["Insights", "Flashcards", "Interactive Learning (beta)"])

    with tab1:
        insights_section(student_id, module_id, subtopics_list)

    with tab2:
        flashcards_section(student_id, module_id, subtopics_list)

    with tab3:
        interactive_learning_section(student_id, module_id, subtopics_list)