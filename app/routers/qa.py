import os
from fastapi import APIRouter, UploadFile, File
from app.data.messages.qa import QuestionAnsweringRequest, QuestionAnsweringResponse, \
    BaseResponseModel
from app.common.log_util import logger
from app.common import manager_util

qa_router = APIRouter(
    prefix="/qa",
    tags=["question answering"],
)

PATH_DOCUMENTS = './documents'


@qa_router.post("/query", response_model=QuestionAnsweringResponse)
async def answer_question(req: QuestionAnsweringRequest):
    logger.info("answer question from user")
    query_text = req.question
    manager = manager_util.get_manager()
    response = manager.query_index(query_text)._getvalue()
    response_text = str(response)
    question_answer_pair = f"question: {query_text}, answer: {response_text}"
    manager.insert_into_index(question_answer_pair)
    return QuestionAnsweringResponse(data=response_text)


@qa_router.get("/documents", response_model=QuestionAnsweringResponse)
async def get_documents_list():
    manager = manager_util.get_manager()
    documents = manager.get_documents_list()._getvalue()
    return QuestionAnsweringResponse(data=documents)


@qa_router.post("/uploadFile", response_model=BaseResponseModel)
def upload_file(uploaded_file: UploadFile = File(..., description="files for indexing"), ):
    manager = manager_util.get_manager()
    try:
        filename = uploaded_file.filename
        filepath = os.path.join(PATH_DOCUMENTS, os.path.basename(filename))
        # save file to local
        with open(filepath, 'wb') as buffer:
            buffer.write(uploaded_file.file.read())
        manager.insert_into_index(filepath, doc_id=filename)
    except Exception as e:
        return BaseResponseModel(msg="File uploaded failed: {}".format(str(e)))
    return BaseResponseModel(msg="File uploaded successfully")
