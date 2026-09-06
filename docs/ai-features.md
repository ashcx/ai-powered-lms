# AI Features

## Purpose

Generative AI is used to turn performance data and learning materials into explanations, revision content, and practical summaries. It supports students and lecturers; it does not replace lecturer judgement or formal assessment.

## Models and services

The project uses OpenAI services for different tasks:

- GPT models for summaries, explanations, chat, question generation, and video scripts
- `text-embedding-3-small` for document and query embeddings
- Text-to-speech for generated narration
- Speech-to-text transcription for caption timings
- FFmpeg for combining background video, narration, and captions

Model selection is handled through the client helper and backend defaults, so future changes do not need to be made in every feature. Further centralising these settings would improve consistency.

## Common AI workflow

Most features follow this pattern:

1. Retrieve student, class, question, or learning-material data.
2. Build a task-specific prompt.
3. Send the request through the FastAPI backend.
4. Stream or parse the response.
5. Display the result in Streamlit.
6. Cache selected responses to avoid repeating the same request during navigation.

## Student features

### Personalised welcome message

The application uses a student’s module-level performance to generate a short, encouraging message. The message is cached in the session so the same page navigation does not repeatedly call the model.

**Limitation:** The message is based on available scores and may not reflect other factors affecting the student’s progress.

### Per-module learning summary

The application sends subtopic-level scores to the model and requests three sections:

- Strong areas
- Areas to improve
- Practical advice

The prompt asks for a concise and approachable explanation without displaying the student’s exact numeric grades.

**Limitation:** The advice is generated from score patterns and should not be treated as a complete diagnosis of learning difficulty.

### Incorrect-answer explanations

Students can open questions they answered incorrectly and request an explanation. Questions are grouped into easy, medium, and hard categories to support targeted revision.

When an explanation is requested, the system first searches learning materials for relevant context. If suitable context is found, the model is instructed to answer from that material and identify the relevant document names. If the similarity score is too low, the system uses a general-knowledge fallback.

**Limitation:** The fallback answer may be less aligned with the course materials. Even RAG-based answers can be incomplete or incorrect.

### AI revision flashcards

The model creates short-answer revision questions from a student’s incorrectly answered questions. The interface presents the question on the front of a card and the answer on the back, with keyboard navigation and an expandable list of cards.

**Limitation:** Generated flashcards need review for accuracy, clarity, and appropriate difficulty.

### Interactive learning environment

Students choose a mode such as learning new content, revision, or explaining mistakes, then select a subtopic. The system:

1. Retrieves relevant learning materials and student context.
2. Generates a short instructional script and learning objectives.
3. Converts the script to narrated audio.
4. Transcribes the audio to obtain caption timings.
5. Combines the audio, captions, and background video with FFmpeg.
6. Displays the generated video and allows follow-up chat.

The chat keeps context from the current session so follow-up questions can refer to the selected topic and previous messages.

**Limitations:** Video generation takes time, uses paid API calls, depends on FFmpeg, and may produce content that needs human review for teaching quality.

## Lecturer features

### Low-performing student analysis

The system identifies the lowest-performing students, analyses their subtopic results, and generates structured focus areas and suggested interventions. A report can also be sent to a lecturer by email.

**Limitations:** The current selection is score-based and should not be used as the sole basis for labelling or intervening with students. Email reporting also requires a secure provider configuration before public deployment.

### Class performance summary

The model converts cohort-level statistics into plain-language observations that help lecturers identify areas for follow-up.

**Limitation:** Summaries describe the available metrics but cannot establish why a class performed poorly without additional context.

### Common-mistake summary

Questions missed by a large proportion of the class are identified and grouped by topic. The model summarises the likely weak areas so lecturers can plan revision or provide additional material.

**Limitation:** The current threshold is fixed and may not be appropriate for every class size, assessment, or question difficulty.

## Retrieval-augmented generation

The RAG pipeline stores learning-material chunks and their embeddings in PostgreSQL with `pgvector`. For a question:

1. The question is converted into an embedding.
2. A Supabase SQL function performs a vector similarity search.
3. The top matching chunks are returned with metadata such as document name and module.
4. The chunks are added to the prompt.
5. The model answers from the retrieved context when it is sufficiently relevant.

The current implementation retrieves a small number of top matches and falls back when the best similarity score is below the configured threshold.

## Prompting and response control

Prompts define the audience, tone, task, expected length, and output structure. Some features request a specific format, such as headings, bullet points, or JSON, so that the Streamlit interface can use the response consistently.

The synthetic-question generator also supplies the module, subtopic, and learning-material outline. Parallel requests are used to speed up question generation, while temperature is adjusted to encourage variety.

## Caching, sessions, and context

Selected summaries and explanations are cached in Streamlit session state. This reduces duplicate requests during navigation. Interactive-learning chat uses the current session’s messages and selected learning context rather than a complete long-term learner profile.

## Safety and human oversight

- Do not send real student information to an AI service without the required approval and safeguards.
- Treat AI output as assistance, not as an official grade or diagnosis.
- Review generated explanations, flashcards, videos, and lecturer reports before relying on them.
- Keep API keys and provider credentials outside source code and version control.

## Limitations

- AI output can hallucinate, misunderstand a question, or give advice that does not fit the student.
- Prompted output is not guaranteed to follow the requested structure every time.
- The current RAG implementation is basic; advanced retrieval, evaluation, and citation checks are not included.
- AI latency and cost increase with the number and length of requests.
- Synthetic data limits how confidently the personalisation can be evaluated.
- Conversation context is session-based rather than a full long-term learner profile.

## Future improvements

- Add automated response checks and course-material citation validation.
- Evaluate RAG quality using a set of teacher-reviewed questions.
- Add metadata filtering and improved context selection.
- Store approved learning preferences and progress with explicit privacy controls.
- Add rate limits, retry handling, usage monitoring, and safer email configuration.

[← Back to README](../README.md)
