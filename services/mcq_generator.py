import requests
from pydantic import BaseModel
BASE_URL = "http://127.0.0.1:8000"


class MCQ(BaseModel):
    question: str
    options: dict[str, str]
    answer: str
    explanation: str
    ref: str


class MCQResponse(BaseModel):
    questions: list[MCQ]


def generate_mcqs(content: str) -> MCQResponse:
    """
    Generate MCQs from a given text content
    """
    res = requests.post(
        f"{BASE_URL}/api/v1/post/azure_answer_response", json={
            'context': content,
            'question': '',
            'no_of_questions': 10
        }, timeout=300)

    return res.json()
