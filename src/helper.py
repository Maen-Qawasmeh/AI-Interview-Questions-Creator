
import re

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import TokenTextSplitter
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.vectorstores import FAISS

from langchain_classic.chains.summarize import load_summarize_chain
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain

from src.prompt import PROMPT_QUESTIONS, REFINE_PROMPT_QUESTIONS


# ==================== PDF LOADING ====================

def load_pdf(file_path: str):
    """
    Load a PDF file and extract its pages as LangChain Documents.
    """

    # Initialize the PDF loader
    loader = PyPDFLoader(file_path)

    # Extract text from all PDF pages
    documents = loader.load()

    return documents


# ==================== TEXT SPLITTING ====================

def split_documents(documents):
    """
    Prepare PDF documents for question and answer generation.
    """

    # Combine text from all PDF pages
    question_gen = "\n".join(
        page.page_content for page in documents
    )

    # Create larger chunks for question generation
    question_splitter = TokenTextSplitter(
        model_name="gpt-3.5-turbo",
        chunk_size=10000,
        chunk_overlap=200
    )

    # Convert text chunks into LangChain Documents
    question_documents = [
        Document(page_content=chunk)
        for chunk in question_splitter.split_text(question_gen)
    ]

    # Create smaller chunks for answer generation
    answer_splitter = TokenTextSplitter(
        model_name="gpt-3.5-turbo",
        chunk_size=1000,
        chunk_overlap=100
    )

    # Split documents into smaller answer chunks
    answer_documents = answer_splitter.split_documents(
        question_documents
    )

    return question_documents, answer_documents


# ==================== QUESTION GENERATION ====================

def generate_questions(question_documents):
    """
    Generate interview questions from CV documents using local Qwen.
    """

    # Initialize local Qwen model
    llm = ChatOllama(
        model="qwen3:4b-instruct",
        temperature=0.3
    )

    # Create question generation and refinement chain
    question_chain = load_summarize_chain(
        llm=llm,
        chain_type="refine",
        question_prompt=PROMPT_QUESTIONS,
        refine_prompt=REFINE_PROMPT_QUESTIONS,
        verbose=False
    )

    # Generate interview questions
    result = question_chain.invoke({
        "input_documents": question_documents
    })

    return result["output_text"]


# ==================== QUESTION PARSING ====================

def parse_questions(questions_text):
    """
    Convert numbered interview questions into a clean list.
    """

    # Split questions based on numbering (1. 2. 3. ...)
    questions_list = re.split(
        r"\s*(?<!\w)(?<!\d)(?=\d{1,3}[\.\)]\s+)",
        questions_text.strip()
    )

    # Remove empty entries and extra whitespace
    questions_list = [
        question.strip()
        for question in questions_list
        if question.strip()
    ]

    return questions_list


# ==================== ANSWER GENERATION (RAG) ====================

def generate_answers(questions_list, answer_documents):
    """
    Generate answers for a batch of interview questions using
    FAISS retrieval and a local Qwen model.
    """

    # ==================== EMBEDDING MODEL ====================

    # Initialize local embedding model
    embeddings = OllamaEmbeddings(
        model="nomic-embed-text"
    )

    # Create FAISS vector store from CV documents
    vector_store = FAISS.from_documents(
        documents=answer_documents,
        embedding=embeddings
    )

    # ==================== DOCUMENT RETRIEVER ====================

    # Configure retriever to fetch relevant CV context
    retriever = vector_store.as_retriever(
        search_kwargs={"k": 3}
    )

    # ==================== ANSWER GENERATION MODEL ====================

    # Initialize Qwen for answer generation
    llm = ChatOllama(
        model="qwen3:4b-instruct",
        temperature=0.1,
        num_predict=350
    )

    # ==================== ANSWER GENERATION PROMPT ====================

    answer_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are an expert technical interview preparation assistant.

Your task is to help a candidate prepare accurate,
professional interview answers using their CV and
general technical knowledge.

CANDIDATE CV CONTEXT:
{context}

STRICT RULES:

1. PERSONAL EXPERIENCE:
   - Only mention projects, achievements, responsibilities,
     tools, and work experience explicitly supported by the CV.
   - Never invent personal experiences, project results,
     company tasks, metrics, or accomplishments.
   - Do not assume that knowing a technology means the
     candidate used it in a specific project.

2. MISSING INFORMATION:
   - If a question asks about personal experience not
     described in the CV, clearly acknowledge that
     those details are not available.
   - Suggest what the candidate could discuss without
     presenting suggestions as actual experiences.

3. TECHNICAL QUESTIONS:
   - Explain technical concepts using accurate
     general knowledge.
   - Provide practical examples when useful.
   - Clearly identify hypothetical examples.

4. ANSWER QUALITY:
   - Write in professional, natural English.
   - Aim for approximately 100–150 words.
   - Focus directly on the interview question.
   - Avoid unnecessary introductions and repetition.
   - Use first-person statements only for verified CV facts.

5. MARKDOWN FORMATTING:
   - Use short paragraphs.
   - Use bullet points when appropriate.
   - Use **bold** for important technical terms.
   - Put each bullet on a separate line.
   - Avoid large headings and complex formatting.

6. HONESTY:
   - Never fabricate information to make the
     candidate appear more experienced.
   - When evidence is insufficient, be transparent.

Generate a concise and useful interview preparation answer
following all the rules above."""
        ),
        ("human", "{input}")
    ])

    # ==================== CREATE RAG CHAINS ====================

    # Combine retrieved documents with the answer prompt
    document_chain = create_stuff_documents_chain(
        llm=llm,
        prompt=answer_prompt
    )

    # Create retrieval-augmented generation pipeline
    answer_chain = create_retrieval_chain(
        retriever,
        document_chain
    )

    # ==================== BATCH ANSWER GENERATION ====================

    results = []

    # Generate answers only for the current batch
    for question in questions_list:

        question = question.strip()

        if not question:
            continue

        # Retrieve relevant context and generate an answer
        response = answer_chain.invoke({
            "input": question
        })

        # Store question and generated answer
        results.append({
            "question": question,
            "answer": response["answer"]
        })

    return results
