import os
import json
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional

from supabase import create_client
from langchain_community.embeddings import OpenAIEmbeddings
from openai import OpenAI

load_dotenv()
SUPABASE_URL         = os.getenv("SUPABASE_URL")
SUPABASE_KEY         = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY")

SIMILARITY_THRESHOLD = 0.02  # reject queries when best hit is below this

supabase             = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client        = OpenAI(api_key=OPENAI_API_KEY)
embedder             = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)


app = FastAPI()

class QueryRequest(BaseModel):
    query: str
    k: int = 5
    module_id: str

# For simple chat requests (no k/module_id)
class ChatRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    answer: Optional[str]
    sources: list[str] = []


# hhelper functions
def build_messages(system_prompt: str, user_prompt: str):
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt}
    ]

def openai_stream_generator(messages: list[dict], model: str = 'gpt-4.1-mini-2025-04-14', temperature: float = 0.6):
    """
    OpenAI streaming generator: yields each token from the chat completion.
    """
    stream = openai_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=True
    )
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token


def openai_non_stream_generator(messages: list[dict], model: str = 'gpt-4.1-mini-2025-04-14', temperature: float = 0.6):
    resp = openai_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=False
    )

    return resp.choices[0].message.content or "", resp.choices[0].finish_reason


def fetch_top_k(vec, k, module_id):
    rows = (supabase.rpc("match_documents", 
    {"in_module_id": module_id, "query_embedding": vec, "match_count": k}
    ).execute().data or [])
    
    for r in rows:
        r["similarity"] = float(r.get("similarity", 0))
    print("rows from rpc", len(rows), "\n", rows)
    return rows
    

def require_user(token: str | None = None):
    # In production, verify JWT & return claims (skip for brevity)
    return {"uid": "demo"}   


# endpoints
@app.post("/stream-explain")
async def stream_explain(req: QueryRequest, user=Depends(require_user)):
    # 1) Embed the query
    q_vec = embedder.embed_query(req.query)

    # 2) Retrieve top-k documents
    docs = fetch_top_k(q_vec, req.k, req.module_id)
    
    if not docs or docs[0]["similarity"] < SIMILARITY_THRESHOLD:
        # Fallback to general knowledge (or internet search) if no RAG context
        fallback_messages = [
            {"role": "system", "content":
                "You are a knowledgeable data-analytics tutor. Your users are students studying a degree in data analytics. They need your answers and help in answering some quiz/test questions they got wrong. "
                "Ensure that your answers are easy-to-follow and concise, so that students will be more likely to read and understand to them. "
                "If you cite information, indicate the source in brackets."
            },
            {"role": "user", "content": f"Question: {req.query}"}
        ]
        return StreamingResponse(
            openai_stream_generator(fallback_messages, temperature=0.7),
            media_type="text/plain; charset=utf-8"
        )

    # 3) Build the combined context
    context = "\n\n".join(str(item) for item in docs)
    prompt = [
        {"role": "system", "content":
          "You are a helpful tutor. Your users are students studying a degree in data analytics. They need your answers and help in answering some quiz/test questions they got wrong. "
          "Ensure that your answers are easy-to-follow and concise, so that students will be more likely to read and understand to them. "},
        {"role": "user",   "content":
          f"Context:\n{context}\n\nAnswer the following strictly from the context above. "
          f"If no relevant context, say you don't know.\n\nQuestion: {req.query}"
          "The data sources provided are from lecture materials related to a specific topic. "
          "If the data sources are not sufficient to answer the question, respond with 'I am not sure based on the given information.' In that case, do not give any other answer."
          "If the data sources are sufficient to answer the question, answer the question based on the data sources."
          "Answer the question in a way that is easy to understand. Aim to use bullet points where appropriate, though this is not always necessary. "
          "Answer in this format: [Your Answer] \n\nSources: [document_name 1, document_name 2, ...]"
          "The sources MUST BE CITED from the 'document_name' parameter in the context above. DO NOT NAME YOUR SOURCES FROM THE CONTENT ITSELF."
          "Only cite the resources that are integral to answering the question. Do not cite resources that are not relevant to the question, even if they were in the prompt."}
    ]

    source_ids = [d["chunk_id"] for d in docs]
    # 4) Generate RAG-based response into buffer
    rag_tokens = []
    for token in openai_stream_generator(prompt, model="gpt-4.1-mini-2025-04-14", temperature=0.5):
        rag_tokens.append(token)
    rag_response = "".join(rag_tokens)

    # 5) If fallback phrase detected, use AI general knowledge
    if "I am not sure" in rag_response:
        fallback_messages = [
            {"role": "system", "content":
                "You are a knowledgeable data-analytics tutor. Your users are students studying a degree in data analytics. They need your answers and help in answering some quiz/test questions they got wrong. "
                "Ensure that your answers are easy-to-follow and concise, so that students will be more likely to read and understand to them. "
                "If you cite information, indicate the source in brackets. Limit your response to 200 tokens max."
            },
            {"role": "user", "content": f"Question: {req.query}"}
        ]
        return StreamingResponse(
            openai_stream_generator(fallback_messages, model="gpt-4.1-mini-2025-04-14", temperature=0.7),
            media_type="text/plain; charset=utf-8",
            headers={"X-RAG-Sources": json.dumps(source_ids)}
        )

    # 6) Otherwise, stream the original RAG response
    return StreamingResponse(
        iter(rag_tokens),
        media_type="text/plain; charset=utf-8",
        headers={"X-RAG-Sources": json.dumps(source_ids)}
    )


# call chatgpt directly
@app.post("/chat")
async def chat(req: ChatRequest, model: str = "gpt-4.1-mini-2025-04-14", temperature: float = 0.7, user=Depends(require_user), stream: bool = True):
    # Build standard OpenAI chat messages
    if stream:
        messages = build_messages("", req.query)
        return StreamingResponse(
            openai_stream_generator(messages, model=model, temperature=temperature),
            media_type="text/plain; charset=utf-8"
        )
    else:
        messages = build_messages("", req.query)
        content, finish_reason = openai_non_stream_generator(messages, model=model, temperature=temperature)
        return PlainTextResponse(content, media_type="text/plain; charset=utf-8", headers={"X-Finish-Reason": finish_reason})


# ---------- non student-specific data endpoints ----------

# CREATE OR REPLACE FUNCTION enumerate_modules()
# RETURNS TABLE(module_id TEXT) AS $$
#   SELECT DISTINCT module_id FROM quiz_df;
# $$ LANGUAGE SQL STABLE;
@app.get("/enumerate_modules")
def enumerate_modules(user=Depends(require_user)):
    resp = supabase.rpc("enumerate_modules").execute()
    if resp.data:
        return resp.data
    else:
        return None

# CREATE OR REPLACE FUNCTION enumerate_subtopics(p_module_id TEXT)
# RETURNS TABLE(subtopic TEXT) AS $$
#   SELECT DISTINCT subtopic
#   FROM quiz_df AS q
#   WHERE q.module_id = p_module_id;
# $$ LANGUAGE SQL STABLE;

@app.get("/enumerate_subtopics/{module_id}")
def enumerate_subtopics(module_id: str, user=Depends(require_user)):
    resp = supabase.rpc("enumerate_subtopics", {"p_module_id": module_id}).execute()
    if resp.data:
        return resp.data
    else:
        return None


# ---------- student-specific data endpoints ----------

@app.get("/subjects/{student_id}")
def subjects(student_id: str, user=Depends(require_user)):
    resp = supabase.rpc("get_weighted_scores", {"p_student_id": student_id}).execute()
    if resp.data:
        return resp.data
    else:
        return None

@app.get("/subtopics/{student_id}/{module_id}")
def subtopics(student_id: str, module_id: str, user=Depends(require_user)):
    resp = supabase.rpc("get_subtopic_scores", {"p_student_id": student_id, "p_module_id": module_id}).execute()
    if resp.data:
        return resp.data
    else:
        return None

@app.get("/correct_wrong_questions/{student_id}/{module_id}/{subtopic}")
##################### WIP ######################
def correct_wrong_questions(student_id: str, module_id: str, subtopic: str, user=Depends(require_user)):
    resp = supabase.rpc("get_correct_wrong_questions", {"p_student_id": student_id, "p_module_id": module_id, "p_subtopic": subtopic}).execute()
    if resp.data:
        return resp.data
    else:
        return None

# ---------- student-specific data endpoints ----------
@app.get("/all_subjects")
def all_subjects(user=Depends(require_user)):
    resp = supabase.rpc("all_subjects").execute()
    if resp.data:
        return resp.data
    else:
        return None

@app.post("/feedback")
def feedback(body: dict, user=Depends(require_user)):
    supabase.table("llm_feedback").insert(body).execute()
    return {"status": "recorded"}

@app.get("/get_top_students")
def get_top_students(n: int = Query(10, ge=1, le=100)):
    resp = supabase.rpc("get_top_n", {"p_limit": n}).execute()
    if resp.data:
        return resp.data
    else:
        return None

@app.get("/get_last_students")
def get_last_students(n: int = Query(10, ge=1, le=100)):
    resp = supabase.rpc("get_last_n", {"p_limit": n}).execute()
    if resp.data:
        return resp.data
    else:
        return None

@app.get("/overall_summary")
def overall_summary(user=Depends(require_user)):
    resp = supabase.rpc("overall_summary").execute()
    if resp.data:
        return resp.data
    else:
        return None

@app.get("/avg_subtopic_scores/{module_id}")
def avg_subtopic_scores(module_id: str, user=Depends(require_user)):
    resp = supabase.rpc("avg_subtopic_scores", {"p_module_id": module_id}).execute()
    if resp.data:
        return resp.data
    else:
        return None

@app.get("/module_wrong_questions/{module_id}")
def module_wrong_questions(module_id: str, user=Depends(require_user)):
    resp = supabase.rpc("module_wrong_questions", {"p_module_id": module_id}).execute()
    if resp.data:
        return resp.data
    else:
        return None

@app.get("/get_documents/{module_id}")
def get_documents(module_id: str, user=Depends(require_user)):
    resp = supabase.table('doc_chunks').select('chunk_id', 'content').eq('module_id', module_id).execute()
    if resp.data:
        return resp.data
    else:
        return None