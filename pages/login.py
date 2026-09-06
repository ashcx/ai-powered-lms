import streamlit as st
import os, requests, time, json, re
from streamlit.components.v1 import html    
from streamlit import session_state

USERS = {
    "student001": {"pwd": "letmein", "id": "S01"},
    "student002": {"pwd": "letmein", "id": "S02"},
    "student003": {"pwd": "letmein", "id": "S03"},
    "student004": {"pwd": "letmein", "id": "S04"},
    "student005": {"pwd": "letmein", "id": "S05"},
    "student006": {"pwd": "letmein", "id": "S06"},
    "student007": {"pwd": "letmein", "id": "S07"},
    "student008": {"pwd": "letmein", "id": "S08"},
    "student009": {"pwd": "letmein", "id": "S09"},
    "student010": {"pwd": "letmein", "id": "S10"},
    "student011": {"pwd": "letmein", "id": "S11"},
    "student012": {"pwd": "letmein", "id": "S12"},
    "student013": {"pwd": "letmein", "id": "S13"},
    "student014": {"pwd": "letmein", "id": "S14"},
    "student015": {"pwd": "letmein", "id": "S15"},
    "student016": {"pwd": "letmein", "id": "S16"},
    "student017": {"pwd": "letmein", "id": "S17"},
    "student018": {"pwd": "letmein", "id": "S18"},
    "student019": {"pwd": "letmein", "id": "S19"},
    "student020": {"pwd": "letmein", "id": "S20"},
    "student021": {"pwd": "letmein", "id": "S21"},
    "student022": {"pwd": "letmein", "id": "S22"},
    "student023": {"pwd": "letmein", "id": "S23"},
    "student024": {"pwd": "letmein", "id": "S24"},
    "student025": {"pwd": "letmein", "id": "S25"},
    "student026": {"pwd": "letmein", "id": "S26"},
    "student027": {"pwd": "letmein", "id": "S27"},
    "student028": {"pwd": "letmein", "id": "S28"},
    "student029": {"pwd": "letmein", "id": "S29"},
    "student030": {"pwd": "letmein", "id": "S30"},
    "student031": {"pwd": "letmein", "id": "S31"},
    "student032": {"pwd": "letmein", "id": "S32"},
    "student033": {"pwd": "letmein", "id": "S33"},
    "student034": {"pwd": "letmein", "id": "S34"},
    "student035": {"pwd": "letmein", "id": "S35"},
    "student036": {"pwd": "letmein", "id": "S36"},
    "student037": {"pwd": "letmein", "id": "S37"},
    "student038": {"pwd": "letmein", "id": "S38"},
    "student039": {"pwd": "letmein", "id": "S39"},
    "student040": {"pwd": "letmein", "id": "S40"},
    "student041": {"pwd": "letmein", "id": "S41"},
    "student042": {"pwd": "letmein", "id": "S42"},
    "student043": {"pwd": "letmein", "id": "S43"},
    "student044": {"pwd": "letmein", "id": "S44"},
    "student045": {"pwd": "letmein", "id": "S45"},
    "student046": {"pwd": "letmein", "id": "S46"},
    "student047": {"pwd": "letmein", "id": "S47"},
    "student048": {"pwd": "letmein", "id": "S48"},
    "student049": {"pwd": "letmein", "id": "S49"},
    "student050": {"pwd": "letmein", "id": "S50"},
}
TEACHERS = {                # demo teacher credentials
    "teacher_anna": "letmein",
    "teacher_bob":  "letmein",
}

def login_view():
    if st.button("← Back to Home", key="back_home"):
        st.session_state.stage = "home"
        st.rerun()

    st.subheader("🔐 Login")
    tab1, tab2 = st.tabs(["Student", "Teacher"])

    with tab1:
        u = st.text_input("Student username")
        p = st.text_input("Password", type="password")
        if st.button("Log in as Student"):
            if u in USERS and USERS[u]["pwd"] == p:
                st.session_state.stage = "student_dashboard"
                st.session_state.role = "student"
                st.session_state.user_id = USERS[u]["id"]
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        u = st.text_input("Teacher username", key="tu")
        p = st.text_input("Password", key="tp", type="password")
        if st.button("Log in as Teacher"):
            if TEACHERS.get(u) == p:
                st.session_state.stage = "teacher_dashboard"
                st.session_state.role = "teacher"
                st.session_state.user_id = u
                st.rerun()
            else:
                st.error("Invalid credentials")