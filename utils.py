import langchain
from pinecone import Pinecone
from langchain_openai import ChatOpenAI
from langchain.chains.summarize import load_summarize_chain
from langchain_community.vectorstores import Pinecone as pine
import os
from dotenv import load_dotenv
load_dotenv()

pc = Pinecone(
   api_key= os.getenv("PINECONE_API_KEY"),  
   environment= os.getenv("PINECONE_ENV"),  
)

print(pc)

def pull_from_pinecone(pinecone_apikey, pinecone_environment, pinecone_index_name, embedding, docs):
    Pinecone(api_key=pinecone_apikey, environment=pinecone_environment)
    global index
    index = pine.Index(index_name=pinecone_index_name)
    return index 
    
def get_summary(doc):
    llm_g = ChatOpenAI(model="gpt-3.5-turbo-0125", temperature=0)
    chain = load_summarize_chain(llm_g, chain_type="map_reduce")
    summary = chain.run([doc])
    return summary

def similar_doc(query, pinecone_apikey, pinecone_environment, pinecone_index_name, embedding):
    Pinecone(api_key=pinecone_apikey, environment=pinecone_environment)
    docsearch = pine.from_existing_index(pinecone_index_name, embedding)
    similar_docs = docsearch.similarity_search_with_score(query, k=15)
    return similar_docs

def refined_data(combined_text):
    prompt = f"""Your task is to refine the provided data for further processing. While keeping plain data as it is, your goal is to restructure any tabular data or other structured forms into a more organized format such as JSON.

                Ensure that the restructuring maintains the integrity of the data and facilitates easier processing and analysis in subsequent steps.

                Strive to make the refined data more readable, accessible, and compatible with various processing methods and tools.

                Your refined data should retain all relevant information while enhancing its structure for improved usability and efficiency in downstream tasks.

                data :- {combined_text}
                """
    llm = ChatOpenAI(model="gpt-3.5-turbo-0125", temperature=0)
    data = llm.invoke(prompt)
    return data.content
    

def generated_answer(query, text):
    prompt = f"""Imagine you are stardandise in responding to user's query
                
                Your goal is to review the data provided and identify opportunities to further tailor the information to the user's specific query and context. 
                
                Ensure that the data effectively addresses the user's needs.

                Strive to make the refined response informative, engaging, and persuasive, instilling confidence in the user's ability to leverage technology effectively to drive innovation and success within their practice.
                
                Strictly don't write anything that is irrelevant to user's query like any greeting message or anything etc.

                query :- {query}
                data :- {text}
                """
    llm = ChatOpenAI(model="gpt-3.5-turbo-0125", temperature=0)
    response = llm.invoke(prompt)
    return response.content