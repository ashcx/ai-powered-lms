import streamlit as st
from datetime import datetime
from streamlit.components.v1 import html
import streamlit.components.v1 as components

from api.client import *
from components.charts import web_chart, plt_boxplot
from components.email import send_email
import pandas as pd

def teacher_dashboard():
    # Button styles
    with open("button_styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    st.header("👩‍🏫 Welcome, Teacher!")

    tab1, tab2 = st.tabs(["Insights", "Teacher dashboard"])

    with tab1:
        # Fetch metrics (class averages per module)
        modules = get_teacher_subjects()
        if not modules:
            st.info("No modules found.")
            return

        # === Module cards =========================================================
        st.subheader("Your Classes")
        cols = st.columns(3)
        for idx, mod in enumerate(modules):
            mod_id = mod["module_id"]
            with cols[idx % 3]:
                pct = mod.get("class_avg", "—")
                if st.button(f"{mod_id}", key=f"tmod_{mod_id}", use_container_width=True):
                    st.session_state.selected_module = mod_id
                    st.session_state.stage = "teacher_module"
                    st.rerun()

        st.divider()

        # === Cohort Leaderboard ===================================================
        st.subheader("Student leaderboard (all classes)")
        n_students = 10
        top = get_top_students(n_students)
        low = get_last_students(n_students)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Top {n_students} Students**")
            web_chart([row['student_id'] for row in top], [row['overall_score'] for row in top],
                    sort='descending', unit='%', height=400)
        with col2:
            st.markdown(f"**Bottom {n_students} Students**")
            web_chart([row['student_id'] for row in low], [row['overall_score'] for row in low],
                    sort='ascending', unit='%', height=400)

        # === Individual worst performing student summary ========================
        st.divider()
        st.subheader("Attention is all they need")
        st.markdown('Explore an in-depth analysis of the strengths and weaknesses of the lowest-performing students.')

        low_student_ids = [row['student_id'] for row in low]

        #====================
        if low_student_ids:

            # overwrite the initial button styles to show the default streamlit button rather than customised one
            # with open("button_styles_default.css") as f:
            #     st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

            # Initialise selection: first student pre‑selected
            if "selected_student_main" not in st.session_state or st.session_state["selected_student_main"] not in low_student_ids:
                st.session_state["selected_student_main"] = None

            # Two-column selector: choose student and then their module
            col1, col2 = st.columns(2)

            # Student selection radio in first column
            with col1:
                selected_student = st.radio(
                    "Student",
                    options=low_student_ids,
                    index=low_student_ids.index(st.session_state["selected_student_main"]) if st.session_state["selected_student_main"] else None,
                    key="selected_student_radio"
                )
            st.session_state["selected_student_main"] = selected_student
            
            with st.spinner("Fetching modules for selected student"):
                # Fetch the modules for the selected student
                #[{"module_id":"DAVA","avg_quiz_score":77.5,"avg_test_score":88.0,"weighted_score":85}, ....]
                subjects_and_scores = get_student_subjects(selected_student)
                modules = [s["module_id"] for s in subjects_and_scores] 
                scores = {module['module_id']: module['weighted_score'] for module in subjects_and_scores}

            # Ensure a default module is set
            if "selected_student_module" not in st.session_state or st.session_state["selected_student_module"] not in modules:
                st.session_state["selected_student_module"] = None

            # Module selection radio in second column
            with col2:
                selected_module = st.radio(
                    "Module",
                    options=[f"{m}: {scores[m]:.1f}%" for m in modules],
                    index=modules.index(st.session_state["selected_student_module"]) if st.session_state["selected_student_module"] else None,
                    key="selected_student_module_radio"
                )
            module_id = st.session_state["selected_student_module"] = selected_module.split(":")[0] if selected_module else None

            subtopics_for_module = enumerate_subtopics(module_id)

            # st.subheader("Incorrectly answered questions:")
            for s in subtopics_for_module:
                if f"incorrect_questions_{selected_student}_{selected_module}_{s['subtopic']}" in st.session_state:
                    st.write(st.session_state[f"incorrect_questions_{selected_student}_{selected_module}_{s['subtopic']}"])
                else:
                    with st.spinner("Getting AI insights for selected student"):
                        st.markdown(f"#### {s['subtopic']}")
                        incorrectly = [
                                q["question_text"]
                                for q in get_correct_wrong_questions(selected_student, module_id, s["subtopic"])
                            if not q["is_correct"]
                        ]

                        prompt = f'''
                        You are given a list of questions that a student has answered incorrectly. 
                        Your task is to generate a short summary of the questions and provide insights on how to improve the student's performance. 
                        Your target audience is teacher who is teaching the student the module {selected_module}. 
                        The subtopic is {s['subtopic']}. 
                        The questions are: {incorrectly}
                        
                        Keep your responses into max 100 words. Use concise, simple language and keep your sentences short and readable. 
                        Use vocabulary that is easy to understand and used in everyday communication. 
                        Answer in Markdown-specific format:
                        **Summary:** [new line]
                        [summary text goes here] [new line]
                        **Current strengths:** [new line]
                        •  Point 1 [new line]
                        •  Point 2 [new line]
                        •  Point 3 [new line]

                        **Focus areas for improvement:** [new line]
                        •  Point 1 [new line]
                        •  Point 2 [new line]
                        •  Point 3 [new line]
                        '''

                        if incorrectly:
                            st.write_stream(chat_stream(prompt, cache_key=f"incorrect_questions_{selected_student}_{selected_module}_{s['subtopic']}"))
                        else:
                            st.write("No feedback available.")
            
        st.markdown("---")
        st.subheader("📧 Email report of students requiring attention")

        # Streamlit form for sending email
        with st.form(key='email_form'):
            teacher_email = st.text_input(
                "Teacher's Email for report",
                placeholder="teacher@example.com",
                key="weak_students_email"
            )
            submit = st.form_submit_button(label='Send Weak Students Report')
            if submit:
                if not teacher_email:
                    st.error("Please enter a valid teacher email address.")
                else:
                    success = send_email(
                        to_email=teacher_email,
                        df=pd.DataFrame(low)
                    )
                    if success:
                        st.success(f"Weak students report sent to {teacher_email}.")
                    else:
                        st.error(f"Failed to send email to {teacher_email}.")

    with tab2:
        st.markdown("#### Teacher Overview Dashboard")
        components.iframe(
            "https://public.tableau.com/views/lecturerchart1/Dashboard1?:embed=y&:showVizHome=no",
            width=1024,
            height=768,
            scrolling=True
        )

    

def teacher_module_page(module_id: str):
    st.button("← Back", on_click=lambda: st.session_state.update({"stage": "teacher_dashboard"}))
    st.header(f"📗 {module_id} — class overview")

    # ---------- AI summary -----------------
    st.subheader("AI summary of class performance")
    sum_key = f"class_summary_{module_id}"

    if sum_key not in st.session_state:
        with st.spinner("Generating AI insights…"):
            resp = overall_summary()
            all_module_summary = pd.DataFrame(resp)
            module_summary = all_module_summary[all_module_summary['module_id'] == module_id].reset_index(drop=True)
            other_modules_summary = all_module_summary[all_module_summary['module_id'] != module_id].reset_index(drop=True)

            module_summary_describe = module_summary.describe()

            other_model_summaries = {}
            for other_module in other_modules_summary['module_id'].unique():
                other_model_summaries[other_module] = other_modules_summary[other_modules_summary['module_id'] == other_module].describe()
            
            prompt = f'''You are writing a brief summary of a class-level performance in a school subject {module_id}. 
            Your aim is to summarise the performance of the class in {module_id} subject. Then, you should aim to 
            perform simple comparisons with the results of the same class in other subjects. 

            Summary of {module_id}:
            {module_summary_describe}

            Summary of other subjects:
            {other_model_summaries}

            Keep your responses into max 300 words. Use concise, simple language and keep your sentences short and readable. 
            Use vocabulary that is easy to understand and used in everyday communication. 

            Here is a rough structure you can follow for your responses:
            [Quantify the performance of the class in {module_id} subject]
            [Compare the performance of the class in {module_id} subject with other subjects]
            [Summarise and suggest possible actions to be taken based on the findings above,]
            '''
            st.write_stream(
                chat_stream(prompt, cache_key=sum_key)
            )

            ##### ADD POSSIBLE DIAGRAM 
    else:
        st.write(st.session_state[sum_key])

    # ---------- Subtopic means -------------
    st.divider()
    st.subheader("Subtopic averages")
    subtopic_scores = pd.DataFrame(avg_subtopic_scores(module_id))
    
    # Prepare data for boxplot: distribution of weighted scores per subtopic
    grouped = subtopic_scores.groupby('subtopic')['weighted_score'].apply(list)
    data = grouped.tolist()
    labels = grouped.index.tolist()

    fig, ax = plt_boxplot(data, x=labels)
    st.pyplot(fig)

    # ---------- Wrong questions ------------
    st.divider()
    st.subheader("Commonly wrong questions")
    st.markdown("Explore the questions and topics that students are weakest at. Select a subtopic to view the wrong questions.")
    wrong_questions = pd.DataFrame(module_wrong_questions(module_id))
    unique_subtopics = wrong_questions['subtopic'].unique()
    
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

    table_data = wrong_questions[wrong_questions['subtopic'] == selected_subtopic]
    table_data.rename(columns={'question_text': 'Question', 'students_who_got_wrong': 'Wrong answers'}, inplace=True)
    table_data = table_data[['Wrong answers', 'Question']]

    # stupid ass formatting for the dataframe to work with longer questions (multi-line auto word wrap)
    row_height = 90
    st.dataframe(
        table_data.reset_index(drop=True),
        use_container_width=True,
        height = (row_height+6) * min(len(table_data), 7),
        hide_index=True,
        row_height = row_height
    )

    st.markdown("\n")
    st.markdown("**Topics students are struggling with:**")
    cache_key = f"insights_{selected_subtopic}_{module_id}_{hash(table_data.to_string())}"
    if cache_key not in st.session_state:
        with st.spinner("Generating AI insights…"):
            
            prompt = f'''The table below shows the wrong answers of students in the {selected_subtopic} subtopic in {module_id} module. 
            
            {table_data}

            Give me ONLY 3-5 bullet points of topics that students are struggling with in this subtopic. 
            You may decide on the number of bullet points at your discretion.

            The format/structure should look like this:
                •  Topic 1
                •  Topic 2
                •  Topic 3
                •  Topic 4
                •  Topic 5
            '''
            
            st.write_stream(
                chat_stream(prompt, cache_key=cache_key)
            )
    else:
        st.write(st.session_state[cache_key])

    # ---------- Student selector chips ----------
    # Collect all student IDs present in this module‑level summary

    st.divider()
    last_10_students = subtopic_scores.groupby(['student_id']).agg({'weighted_score': 'mean' }).sort_values(by='weighted_score').head(10)
    last_10_student_ids = last_10_students.index.tolist()
    
    if last_10_student_ids:
        # Initialise selection: first student pre‑selected
        if "selected_student" not in st.session_state or st.session_state["selected_student"] not in last_10_student_ids:
            st.session_state["selected_student"] = last_10_student_ids[0]

        st.subheader("Top 10 students requiring attention")
        st.markdown("Select a student to view their quiz and test performance by subtopic.")
        # Arrange chips in two rows of up to 5
        rows = [last_10_student_ids[i:i+5] for i in range(0, len(last_10_student_ids), 5)]
        for row in rows:
            cols = st.columns(len(row)) 
            for idx, sid in enumerate(row):
                is_sel = st.session_state["selected_student"] == sid
                label = f"**{sid}**" if is_sel else sid
                if cols[idx].button(label, key=f"student_chip_{sid}"):
                    st.session_state["selected_student"] = sid
        
        # Display below both rows using the selected_student in session state
        selected = st.session_state["selected_student"]

        # selected is the SXX student id
        chart_data = subtopic_scores[subtopic_scores['student_id'] == selected]
        average_quiz_score = chart_data['quiz_score'].mean()
        average_test_score = chart_data['test_score'].mean()
        average_weighted_score = last_10_students.loc[selected]['weighted_score']

        st.markdown(f"Selected student: __{selected}__")
        st.markdown(f"Overall weighted score (including quiz & test): __{average_weighted_score:.1f}%__")
        
        # quiz scores
        st.subheader("Quiz scores")
        st.markdown(f"Average quiz score: __{average_quiz_score:.1f}%__")
        web_chart(chart_data['subtopic'].tolist(), chart_data['quiz_score'].tolist(), unit='%')

        # test scores
        st.subheader("Test scores")
        st.markdown(f"Average test score: __{average_test_score:.1f}%__")
        web_chart(chart_data['subtopic'].tolist(), chart_data['test_score'].tolist(), unit='%')
        
        # Use the chosen student ID in subsequent sections
        student_id = st.session_state["selected_student"]
    else:
        st.warning("No students found for this module.")
        return
