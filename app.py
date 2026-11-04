
from flask import Flask, render_template, request, session
from pathlib import Path
from werkzeug.utils import secure_filename
from uuid import uuid4
import markdown
import bleach
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.helper import (
    load_pdf,
    split_documents,
    generate_questions,
    generate_answers,
    parse_questions
)


# ==================== FLASK APPLICATION ====================

# Initialize Flask application
app = Flask(__name__)

# ==================== MARKDOWN RENDERING ====================

def render_markdown(text):
    """
    Convert Markdown answers into safe HTML.
    """

    # Convert Markdown syntax to HTML
    html = markdown.markdown(text, extensions=["extra"])

    # Sanitize HTML to prevent unsafe content
    clean_html = bleach.clean(
        html,
        tags=[
            "p", "strong", "em", "ul", "ol", "li",
            "h1", "h2", "h3", "h4", "blockquote",
            "code", "pre", "br", "hr", "a"
        ],
        attributes={"a": ["href", "title"]},
        protocols=["http", "https", "mailto"],
        strip=True
    )

    return clean_html


# Register Markdown renderer as a Jinja filter
app.jinja_env.filters["markdown"] = render_markdown


# ==================== SESSION MANAGEMENT ====================

# Secret key for local development only
app.secret_key = os.environ["FLASK_SECRET_KEY"]

# Temporary server-side storage for interview sessions
interview_sessions = {}


# ==================== FILE UPLOAD CONFIGURATION ====================

# Configure PDF upload directory
UPLOAD_FOLDER = Path("static/docs")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


# ==================== HOME PAGE ====================

@app.route("/", methods=["GET", "POST"])
def home():

    # Check incoming HTTP requests
    print("Request Method:", request.method, flush=True)

    if request.method == "POST":

        # ==================== PDF UPLOAD ====================

        # Get the uploaded PDF file
        uploaded_file = request.files.get("pdf_file")

        # Validate the uploaded file
        if not uploaded_file or not uploaded_file.filename:
            return "Please select a PDF file.", 400

        # Validate PDF file extension
        if Path(uploaded_file.filename).suffix.lower() != ".pdf":
            return "Only PDF files are allowed.", 400

        # Generate a safe filename
        filename = secure_filename(uploaded_file.filename)

        # Save the uploaded PDF
        file_path = UPLOAD_FOLDER / filename
        uploaded_file.save(file_path)

        # ==================== PDF PROCESSING ====================

        # Load the uploaded PDF
        documents = load_pdf(str(file_path))

        # Prepare documents for question and answer generation
        question_documents, answer_documents = split_documents(documents)

        # ==================== VERIFY PDF PROCESSING ====================

        print("PDF Pages:", len(documents), flush=True)
        print("Question Documents:", len(question_documents), flush=True)
        print("Answer Documents:", len(answer_documents), flush=True)

        # ==================== QUESTION GENERATION ====================

        # Generate interview questions using the local Qwen model
        questions = generate_questions(question_documents)

        # Convert generated questions into a structured list
        questions_list = parse_questions(questions)

        print("Total Questions:", len(questions_list), flush=True)

        # ==================== FIRST BATCH GENERATION ====================

        # Select the first 5 questions
        first_batch = questions_list[:5]

        # Generate answers using FAISS and Qwen
        answers = generate_answers(
            questions_list=first_batch,
            answer_documents=answer_documents
        )

        print("Total Answers:", len(answers), flush=True)

        # ==================== SAVE INTERVIEW SESSION ====================

        # Generate a unique interview session ID
        session_id = str(uuid4())

        # Store interview data on the server
        interview_sessions[session_id] = {
            "questions": questions_list,
            "answer_documents": answer_documents,
            "answers": answers,
            "next_index": len(first_batch)
        }

        # Store only the session ID in the browser cookie
        session["interview_id"] = session_id

        print("Interview session saved successfully!", flush=True)

        # ==================== DISPLAY RESULTS ====================

        # Check whether additional questions are available
        has_more = len(first_batch) < len(questions_list)

        # Display first batch and Generate More button
        return render_template(
            "index.html",
            answers=answers,
            has_more=has_more
        )

    # ==================== GET REQUEST ====================

    # Display the upload form
    return render_template("index.html")


# ==================== GENERATE MORE QUESTIONS ====================

@app.route("/generate-more", methods=["POST"])
def generate_more():

    # Retrieve the current interview session ID
    session_id = session.get("interview_id")

    # Validate interview session
    if not session_id or session_id not in interview_sessions:
        return "Interview session expired. Please upload your CV again.", 400

    # Retrieve stored interview data
    interview_data = interview_sessions[session_id]

    questions_list = interview_data["questions"]
    answer_documents = interview_data["answer_documents"]
    answers = interview_data["answers"]
    next_index = interview_data["next_index"]

    # ==================== NEXT BATCH ====================

    # Select the next 5 questions
    next_batch = questions_list[next_index:next_index + 5]

    # Check if all questions have been processed
    if not next_batch:
        return render_template(
            "index.html",
            answers=answers,
            has_more=False
        )

    # ==================== ANSWER GENERATION ====================

    # Generate answers only for the next batch
    new_answers = generate_answers(
        questions_list=next_batch,
        answer_documents=answer_documents
    )

    # Append new answers to previous answers
    answers.extend(new_answers)

    # Update the next question index
    interview_data["next_index"] = next_index + len(next_batch)

    # ==================== VERIFY RESULTS ====================

    print("New Answers:", len(new_answers), flush=True)
    print("Total Answers:", len(answers), flush=True)

    # Check whether more questions remain
    has_more = interview_data["next_index"] < len(questions_list)

    # ==================== DISPLAY RESULTS ====================

    # Display all generated answers
    return render_template(
        "index.html",
        answers=answers,
        has_more=has_more
    )


# ==================== RUN APPLICATION ====================

if __name__ == "__main__":
    app.run(
        debug=False,
        use_reloader=False
    )
