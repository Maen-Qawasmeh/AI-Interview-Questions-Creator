from langchain_core.prompts import PromptTemplate

# Prompt for generating interview questions from a candidate's CV
question_template = """
You are an expert technical interviewer specializing in
Artificial Intelligence, Machine Learning, Data Science,
and Software Development.

Generate professional interview questions based on
the candidate's CV provided below.

------------
{text}
------------

Instructions:
1. Generate questions based on the candidate's actual skills and experience.
2. Include technical and practical interview questions.
3. Cover the important topics mentioned in the CV.
4. Do not invent skills or experience.
5. Return only a numbered list of questions.

INTERVIEW QUESTIONS:
"""

# Prompt for refining existing questions using additional CV context
refine_template = """
You are an expert technical interviewer.

Previously generated interview questions:
{existing_answer}

Additional CV context:
------------
{text}
------------

Instructions:
1. Improve existing questions when necessary.
2. Add relevant questions based on new information.
3. Avoid duplicate questions.
4. Do not invent skills or experience.
5. Write all questions in English.
6. If the context adds nothing useful, return the original questions.

INTERVIEW QUESTIONS:
"""

# Create LangChain PromptTemplate objects
PROMPT_QUESTIONS = PromptTemplate(
    template=question_template,
    input_variables=["text"]
)

REFINE_PROMPT_QUESTIONS = PromptTemplate(
    template=refine_template,
    input_variables=["existing_answer", "text"]
)