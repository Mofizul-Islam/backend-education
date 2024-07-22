from typing import List
import asyncio
from pydantic import BaseModel
import aiohttp

BASE_URL = "http://127.0.0.1:8000"


class Question(BaseModel):
    type: str
    question: str
    answer: str
    explanation: str
    ref: str


class MCQ(Question):
    options: dict[str, str]


class MCQResponse(BaseModel):
    questions: List[MCQ]


async def get_questions(question_type: str, content: str, question_count: int, session: aiohttp.ClientSession):
    async with session.post(f"{BASE_URL}/api/v1/post/generate-paper", json={
        'context': content,
        'questions_count': question_count,
        'type': question_type
    }) as res:
        try:
            res = await res.json()
            for question in res['questions']:
                question['type'] = question_type
            return res
        except Exception as e:
            print("Exception processing response", res)
            raise e


async def generate_mcqs(content: str, question_count: int, session: aiohttp.ClientSession) -> MCQResponse:
    """
    Generate MCQs from a given text content
    """
    print("Getting MCQs")
    res = await get_questions("mcq", content, question_count, session)
    return MCQResponse(**res)


class LongAnswerQuestion(BaseModel):
    questions: List[Question]


async def long_questions(content: str, question_count: int, session: aiohttp.ClientSession) -> LongAnswerQuestion:
    """
   Generate long questions from a given text content
    """
    print("Getting Long Questions")
    res = await get_questions("long_question", content, question_count, session)
    return LongAnswerQuestion(**res)


class ShortAnswerQuestion(BaseModel):
    questions: List[Question]


async def short_questions(content: str, question_count: int, session: aiohttp.ClientSession) -> ShortAnswerQuestion:
    """
   Generate short questions from a given text content
    """
    print("Getting Short Questions")
    res = await get_questions("short_question", content, question_count, session)
    return ShortAnswerQuestion(**res)


async def generate_questions(content: str, question_counts: dict[str, int]) -> List[Question]:
    """
    Generate MCQs, long questions, and short questions from a given text content
    """
    async with aiohttp.ClientSession() as session:
        futures = [
            short_questions(
                content, question_counts.get('short_question', 10), session),
            long_questions(content, question_counts.get(
                'long_question', 10), session),
            generate_mcqs(content, question_counts.get('mcq', 10), session)
        ]
        [short_qs, long_qs, mcqs] = await asyncio.gather(*futures)

        print("SHORT QUESTIONS", short_qs)
        print("LONG_QUESTIONS", long_qs)

        questions = short_qs.questions + long_qs.questions + mcqs.questions
        return questions
