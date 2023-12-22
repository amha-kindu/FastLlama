import json
from typing import Any, Dict
from llama_index import (
    Document,
    Prompt,
    SimpleDirectoryReader,
)
from llama_index.response_synthesizers import get_response_synthesizer, ResponseMode
from llama_index.indices.postprocessor import SimilarityPostprocessor
from app.data.models.qa import Source, get_default_answer_id
from app.data.models.mongodb import (
    LlamaIndexDocumentMeta,
    LlamaIndexDocumentMetaReadable,
)
from app.utils.log_util import logger
from app.utils import data_util
from app.llama_index_server.index_storage import index_storage

similarity_cutoff = 0.85
prompt_template_string = (
    "We have provided context information below. \n"
    "---------------------\n"
    "{context_str}"
    "\n---------------------\n"
    "Given this information, assume you are an experienced golf coach, "
    "please give short, simple, accurate, precise answer to the golfer beginner's question, "
    "limited to 80 words maximum. If the question is not relevant to golf, please answer "
    f"'{get_default_answer_id()}'.\n"
    "The question is: {query_str}\n"
)


def query_index(query_text) -> Dict[str, Any]:
    data_util.assert_not_none(query_text, "query cannot be none")
    logger.info(f"Query test: {query_text}")
    # first search locally
    with index_storage.r_index() as index:
        local_query_engine = index.as_query_engine(
            response_synthesizer=get_response_synthesizer(
                response_mode=ResponseMode.NO_TEXT
            ),
            node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=similarity_cutoff)],
        )
        local_query_response = local_query_engine.query(query_text)
    if len(local_query_response.source_nodes) > 0:
        text = local_query_response.source_nodes[0].text
        # todo encapsulate the following text extractions to functions
        if 'answer": ' in text:
            logger.debug(f"Found text: {text}")
            matched_meta = json.loads(text)
            matched_question = matched_meta["question"]
            matched_doc_id = data_util.get_doc_id(matched_question)
            with index_storage.rw_mongo() as mongo:
                doc_meta = mongo.find_one("doc_id", matched_doc_id)
                doc_meta = LlamaIndexDocumentMeta(**doc_meta) if doc_meta else None
                logger.debug(f"Found doc: {doc_meta}")
                if doc_meta:
                    doc_meta.query_timestamps.append(data_util.get_current_milliseconds())
                    mongo.upsert_one("doc_id", matched_doc_id, doc_meta)
                    from_knowledge_base = doc_meta.from_knowledge_base
                else:
                    # means the document has been removed from stored_docs
                    logger.warning(f"'{matched_doc_id}' is not found in stored_docs")
                    doc_meta = LlamaIndexDocumentMeta(
                        doc_id=matched_doc_id,
                        doc_text=text,
                        from_knowledge_base=False,
                        insert_timestamp=data_util.get_current_milliseconds(),
                        query_timestamps=[],
                    )
                    mongo.upsert_one("doc_id", matched_doc_id, doc_meta)
                    from_knowledge_base = False
            answer_text = text.split('answer": ')[1].strip('"\n}')
            if 'category": ' in text:
                category = text.split('category": ')[1].split(",")[0].strip('"\n}')
                category = None if data_util.is_empty(category) else category
            else:
                category = None
            return {
                "category": category,
                "question": query_text,
                "matched_question": matched_question,
                "source": Source.KNOWLEDGE_BASE if from_knowledge_base else Source.USER_ASKED,
                "answer": answer_text,
            }
    # if not found, turn to LLM
    qa_template = Prompt(prompt_template_string)
    with index_storage.r_index() as index:
        llm_query_engine = index.as_query_engine(text_qa_template=qa_template)
        response = llm_query_engine.query(query_text)
    answer_text = str(response)
    # save the question-answer pair to index
    result = {
        "category": None,
        "question": query_text,
        "source": index_storage.current_model,
        "answer": answer_text,
    }
    question_answer_pair = json.dumps(result)
    doc_id = data_util.get_doc_id(query_text)
    insert_text_into_index(question_answer_pair, doc_id)
    return result


def insert_text_into_index(text, doc_id):
    document = Document(text=text)
    insert_into_index(document, doc_id=doc_id)


def insert_file_into_index(doc_file_path, doc_id=None):
    document = SimpleDirectoryReader(input_files=[doc_file_path]).load_data()[0]
    insert_into_index(document, doc_id=doc_id)


def insert_into_index(document, doc_id=None):
    """Insert new document into global index."""
    index_storage.add_doc(document, doc_id)


def delete_doc(doc_id):
    data_util.assert_not_none(doc_id, "doc_id cannot be none")
    logger.info(f"Delete document with doc id: {doc_id}")
    index_storage.delete_doc("doc_id", doc_id)


def get_document(doc_id):
    with index_storage.r_mongo() as mongo:
        doc = mongo.find_one("doc_id", doc_id)
        if doc:
            readable = LlamaIndexDocumentMetaReadable(
                doc_id=doc["doc_id"],
                doc_text=doc["doc_text"],
                from_knowledge_base=doc["from_knowledge_base"],
                insert_timestamp=doc["insert_timestamp"],
                query_timestamps=doc["query_timestamps"],
            )
            return readable
    return None


def cleanup_for_test():
    """cleanup user queries for test"""
    with index_storage.rw_mongo() as mongo:
        return mongo.cleanup_for_test()
