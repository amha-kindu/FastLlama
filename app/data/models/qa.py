from enum import Enum
from pydantic import Field, BaseModel
from typing import Optional

IRRELEVANT_QUESTION = {
    "default_answer_id": "irrelevant_question",
    "default_answer": "This question is not relevant to golf.",
}


def get_default_answer_id():
    return IRRELEVANT_QUESTION["default_answer_id"]


def get_default_answer():
    return IRRELEVANT_QUESTION["default_answer"]


class Source(str, Enum):
    KNOWLEDGE_BASE = "knowledge-base"
    CHATGPT35 = "gpt-3.5-turbo"
    CHATGPT4 = "gpt-4"
    CLAUDE_2 = "claude-2"


class Answer(BaseModel):
    """ """

    category: Optional[str] = Field(
        None, description="Category of the question, if it can be recognized"
    )
    question: str = Field(..., description="the original question")
    source: Source = Field(..., description="Source of the answer")
    answer: str = Field(..., description="answer to the question")

    def __init__(self, **data):
        super().__init__(**data)
        self.answer = self.normalize_answer_for_irrelevant_question(self.answer)

    @staticmethod
    def normalize_answer_for_irrelevant_question(answer: str):
        if answer == IRRELEVANT_QUESTION["default_answer_id"]:
            return IRRELEVANT_QUESTION["default_answer"]
        else:
            return answer
