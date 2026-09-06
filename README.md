# AI-Powered Learning Management System

An MVP learning analytics platform that combines student performance data, interactive dashboards, and generative AI to give students personalised support and help lecturers identify learning gaps.

> **Important:** This project is a prototype built with synthetic data. It is not connected to Temasek Polytechnic's student information systems, and AI-generated advice should be reviewed by a lecturer before being used for academic decisions.

## What the project does

The platform provides two experiences:

- **Students** can view their performance by module and subtopic, receive personalised summaries, explore incorrect answers, practise with AI-generated flashcards, and use the interactive learning environment.
- **Lecturers** can review class performance, identify weak topics and commonly missed questions, inspect high- and low-performing students, and generate targeted summaries.

## Main features

- Synthetic quiz, test, engagement, and learning-material data
- Student and lecturer views in Streamlit
- Supabase PostgreSQL storage and SQL functions
- FastAPI endpoints for application data and AI requests
- Retrieval-augmented explanations using stored learning materials
- AI-generated summaries, explanations, flashcards, scripts, audio, and captions
- Tableau dashboards connected to the database
- K-Means clustering for broad student performance profiles

## Documentation

- [System Architecture](docs/architecture.md)
- [AI Features](docs/ai-features.md)
- [Analytics and Machine Learning](docs/analytics-and-ml.md)

## Technology stack

- Python
- Streamlit 1.46
- FastAPI and Uvicorn
- Supabase and PostgreSQL
- OpenAI API and embeddings
- Tableau
- Pandas, NumPy, Matplotlib, and Seaborn
- FFmpeg for generated video assembly

## Repository structure

```text
app.py                    Streamlit application and page routing
main.py                   FastAPI application and backend endpoints
api/                      Client functions used by the Streamlit app
components/               Charts, email, and video-generation helpers
pages/                    Student, lecturer, and interactive-learning views
notebooks_datasets/       Data-generation, loading, and modelling notebooks
school_submissions/       Academic report and presentation materials
docs/                     Project documentation
requirements.txt          Python dependencies
```

## Running the project locally

### Prerequisites

- Python 3.10 or newer
- A Supabase project containing the required tables, views, SQL functions, and document embeddings
- An OpenAI API key
- FFmpeg installed and available on the system path for interactive video generation

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the environment with:

```powershell
.venv\Scripts\activate
```

### Environment variables

Create a local `.env` file and keep it out of version control:

```env
OPENAI_API_KEY=your_openai_api_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
FAST_API_URL=http://localhost:8000
```

The service-role key is used by the FastAPI backend and must never be exposed in the browser or committed to GitHub. Any email-provider credentials must also be stored as environment variables rather than in source code.

### Start the backend

```bash
uvicorn main:app --reload
```

### Start the Streamlit application

In a second terminal:

```bash
streamlit run app.py
```

The Streamlit app uses `http://localhost:8000` by default for the FastAPI service. Set `FAST_API_URL` if the backend is hosted elsewhere.

## Data and privacy

The project uses synthetic student records for development and demonstration. Do not add real student information, school credentials, private learning materials, or API keys to a public repository. The academic report contains personal and school-specific details, so it should only be published after checking the school’s requirements and removing anything that should remain private.

## Limitations

- The data-generation pipeline produces realistic-looking test data, but it does not prove how real students would behave.
- Integration with a real student information system is proposed, not implemented.
- AI responses can be incomplete, inconsistent, or incorrect and require human review.
- The current RAG implementation is basic and does not include advanced retrieval techniques such as windowing, metadata filtering, or fine-tuning.
- K-Means groups students by patterns in the current dataset; it is not a definitive prediction of academic risk.
- Pages with several AI-powered elements may take longer to render, and AI requests add usage costs.
- The current authentication and email-reporting setup needs further security work before production use.

## Project status and possible next steps

This is a working capstone MVP. Possible next steps include production-grade authentication, safer data access controls, improved RAG retrieval, formal cluster evaluation, real-data validation with approval, better loading states, and a more customisable front end if the system is scaled beyond a prototype.

## Academic materials

The full academic report and presentation materials are stored in [`school_submissions/`](school_submissions/). They provide the project background, literature review, implementation discussion, evaluation, and reflection that sit behind this shorter repository documentation.
