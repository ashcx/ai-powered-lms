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

# Charts UI
from components.charts import web_chart, plt_boxplot

def insights_section(student_id: str, module_id: str, subtopics_list: list):
    # --- AI summary (blocking call, could be streamed with st.write_stream in 1.34+)
    st.subheader("Topic-based summary")

    web_chart([row['subtopic'] for row in get_student_subtopic_scores(student_id, module_id)], 
              [row['weighted_score'] for row in get_student_subtopic_scores(student_id, module_id)], 
              sort='descending', unit='%')

    ## AI summary part
    summary_key = f"summary_{student_id}_{module_id}"
    prompt = (
        f"""
        DATA:
        {get_student_subtopic_scores(student_id, module_id)}

        INSTRUCTIONS:
        The data above is a set of grades that a student has obtained. All of the scores are for a single module in a data analytics course, with each entry representing a different subtopic of the single module.
        Your goal is to provide meaningful analysis of the student's scores in individual subtopics, and give them practical advice to improve their performance in the subtopics that they do poorly in. Write concisely and in an informal but not too casual tone. Write in a way that is easy to understand and fast to read. Aim to use bullet points where appropriate, though this is not always necessary.
        While you may make references to the individual numeric grades and describe them appropriately, do not explicitly include the numeric grade in your response. 
        Group your points into: Strong areas, Areas to improve, Practical advice.
        """.strip()
    )

    if summary_key not in st.session_state:
        with st.spinner("Generating AI insights…"):
            # Stream directly and cache internally
            st.write_stream(chat_stream(prompt, cache_key=summary_key))
    else:
        st.write(st.session_state[summary_key])

    # --- Subtopic list
    st.divider()
    st.subheader("Detailed subtopic analysis")
    st.write("Find out more about your performance in each subtopic.")

    for s in subtopics_list:
        with st.expander(s['subtopic']):
            st.subheader("Incorrectly answered questions:")
            incorrectly = [
                q["question_text"]
                for q in get_correct_wrong_questions(student_id, module_id, s["subtopic"])
                if not q["is_correct"]
            ]
            if not incorrectly:
                st.write("No incorrectly answered questions.")
                continue

            # Show difficulty chips
            levels = ["easy", "medium", "hard"]
            select_key = f"diff_select_{student_id}_{module_id}_{s['subtopic']}"
            if select_key not in st.session_state:
                st.session_state[select_key] = "easy"
            cols = st.columns(3)
            for idx, lvl in enumerate(levels):
                is_sel = st.session_state[select_key] == lvl
                label = f"**{lvl.capitalize()}**" if is_sel else lvl.capitalize()
                if cols[idx].button(label, key=f"{select_key}_{lvl}"):
                    st.session_state[select_key] = lvl
                    # Reset cached categories for this subtopic
                    cache_key = f"cats_{student_id}_{module_id}_{s['subtopic']}"
                    if cache_key in st.session_state:
                        del st.session_state[cache_key]

            choice = st.session_state[select_key]
            cache_key = f"cats_{student_id}_{module_id}_{s['subtopic']}"

            # Only classify when user clicks into this difficulty
            if cache_key not in st.session_state:
                numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(incorrectly))
                prompt = (
                    "Categorize the following questions into easy, medium, and hard levels. "
                    "Respond ONLY with a JSON object mapping categories to lists of question numbers.\n\n"
                    "Questions:\n" + numbered
                )
                with st.spinner("Categorizing question difficulties…"):
                    cats = classify_questions(prompt)
                st.session_state[cache_key] = cats

            # Display selected questions
            cats = st.session_state.get(cache_key, {})
            nums = cats.get(choice, [])
            if nums:
                for n in nums:
                    if 1 <= n <= len(incorrectly):
                        q_text = incorrectly[n-1]
                        st.write(f" •  {q_text}")
                        btn_key = f"explain_{student_id}_{module_id}_{s['subtopic']}_{n}"
                        cache_ans_key = f"answer_{student_id}_{module_id}_{s['subtopic']}_{n}"

                        # placeholder lives across reruns; always create before button logic
                        answer_placeholder = st.empty()

                        # If we already have a cached answer from a previous click, show it immediately.
                        if cache_ans_key in st.session_state:
                            answer_placeholder.info("**Answer:**\n" + st.session_state[cache_ans_key])

                        if st.button("Explain answer", key=btn_key):
                            with st.spinner("Explaining answer…"):
                                full = ""
                                for chunk in stream_explain(
                                        module_id,
                                        f"Explain the answer to: {q_text}",
                                        cache_key=cache_ans_key):
                                    full += chunk
                                    # live update info box as text grows
                                    answer_placeholder.info("**Answer:**\n" + full)
                                # ensure cached final text (stream_explain also caches internally, but double-safe)
                                st.session_state[cache_ans_key] = full
            else:
                st.write(f"No {choice} questions.")