import os, requests, time, json, re, ffmpeg, sib_api_v3_sdk
import streamlit as st
import streamlit.components.v1 as components
from streamlit.components.v1 import html
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import pandas as pd 
from concurrent.futures import ThreadPoolExecutor, as_completed

# within streamlit app
from api.client import *
from components.charts import web_chart, plt_boxplot
from pages.student import student_dashboard, student_module_page
from pages.teacher import *
from pages.login import *
from pages.student_interactive_learning import interactive_learning_section

# -------------------------------------------------------------------
# 0. ENV & CONSTANTS + CHART LAYOUTS
# -------------------------------------------------------------------
load_dotenv()
API_BASE = os.getenv("FAST_API_URL", "http://localhost:8000")  # FastAPI origin

# session‑level STATE
if "stage" not in st.session_state:
    st.session_state.stage = "home"      # home → login → student_dashboard / teacher_dashboard
    st.session_state.user_id = None
    st.session_state.role = None          # "student" | "teacher"
    st.session_state.selected_module = None

# Load global CSS styles from file
with open('global_styles.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Constrain the main Streamlit block container to 1060px
def wide_width():
    st.markdown(
        '''
        <style>
        /* Target the main block container */
        .stMainBlockContainer.block-container {
            max-width: 1060px !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }
        </style>
        ''',
        unsafe_allow_html=True
    )

def normal_width():
    st.markdown(
        '''
        <style>
        /* Target the main block container */
        .stMainBlockContainer.block-container {
            max-width: 800px !important;
        }
        </style>
        ''',
        unsafe_allow_html=True
    )

# -------------------------------------------------------------------
# HOME PAGE WITH OVERVIEW DASHBOARDS
# -------------------------------------------------------------------
def home_view():

    wide_width()

    st.title("🏫 AI‑Enhanced Student Support Portal")
    st.markdown("""
    Welcome! Below you can explore our live dashboards for students and teachers.  
    Click **Log In** anytime to access your personalized workspace.
    """)


    # Centered login button
    if st.button("🔐 **Login for Personalized Support**"):
        st.session_state.stage = "login"


    # Two Tableau embeds side‑by‑side
    st.divider()
    st.markdown("#### Overall Summary of Results")
    components.iframe(
        "https://public.tableau.com/views/studentchart/Dashboard1?:embed=y&:showVizHome=no",
        width=1024,
        height=768
    )



# router
if st.session_state.stage == "home":
    home_view()

elif st.session_state.stage == "login":
    normal_width()
    login_view()

elif st.session_state.stage == "student_dashboard":
    normal_width()
    student_dashboard(st.session_state.user_id)

elif st.session_state.stage == "student_module":
    normal_width()
    student_module_page(st.session_state.user_id, st.session_state.selected_module)

elif st.session_state.stage == "interactive_learning":
    normal_width()
    # show the inline interactive learning section
    subtopics_list = enumerate_subtopics(st.session_state.selected_module)
    interactive_learning_section(
        st.session_state.user_id,
        st.session_state.selected_module,
        subtopics_list
    )

elif st.session_state.stage == "interactive_learning_fullscreen":
    normal_width()
    # render the fullscreen interactive learning page
    from pages.student_interactive_learning_fullscreen import fullscreen_section
    fullscreen_section(
        st.session_state.get("_il_student_id"),
        st.session_state.get("_il_module_id"),
        st.session_state.get("_il_subtopics")
    )

elif st.session_state.stage == "teacher_dashboard":
    normal_width()
    teacher_dashboard()

elif st.session_state.stage == "teacher_module":
    normal_width()
    teacher_module_page(st.session_state.selected_module)

else:
    st.error("Unknown state – try refreshing.")