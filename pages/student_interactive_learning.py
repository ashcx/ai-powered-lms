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
)

# UI Components
from components.charts import web_chart, plt_boxplot
from components import movie as mtc

print(os.getcwd())

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        st.error("FFmpeg is not installed. Please install ffmpeg to use this feature. ")
        return False
    else:
        return True



def interactive_learning_section(student_id: str = None, module_id: str = None, subtopics_list: list = []):
    st.markdown("Make learning as fun as doom-scrolling TikTok!")
    st.markdown("Or chatting with friends on IG")
    st.markdown("Pick a mode, then enjoy a TikTok-style (read: brainrot) video.")
    st.markdown("You can then ask questions, chat with our friendly AI, and have fun time learning!")

    if not check_ffmpeg():
        st.error("FFmpeg is not installed. Please install ffmpeg to use this feature. ")
        return
    else:
        if st.button("🖥️  Open Interactive Learning in Fullscreen", use_container_width=True):
            # Persist identifiers for the fullscreen page
            st.session_state["_il_student_id"] = student_id
            st.session_state["_il_module_id"] = module_id
            st.session_state["_il_subtopics"] = subtopics_list
            # Navigate to the fullscreen page via Streamlit routing
            st.switch_page("pages/student_interactive_learning_fullscreen.py")
            st.session_state.stage = "interactive_learning_fullscreen"
            st.stop()