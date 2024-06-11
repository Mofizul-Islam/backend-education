import streamlit as st
from utils import *
from langchain_community.embeddings import OpenAIEmbeddings

pinecone_apikey = os.getenv("PINECONE_API_KEY")
pinecone_environment = os.getenv("PINECONE_ENV_REGION")
pinecone_index_name = os.getenv("INDEX_NAME")


st.set_page_config("SmartSearch")

st.title("NLP SmartSearch")

query = st.text_input("Enter Your Query:- ")
button = st.button("Generate")

if query and button:
    with st.spinner("Generating Response..."):
        embeddings =  OpenAIEmbeddings()
        relevant_docs = similar_doc(query,pinecone_apikey, pinecone_environment, pinecone_index_name, embeddings)
        combined_str = ""
        for doc in relevant_docs:
            combined_str += doc[0].page_content
        # st.write(combined_str)
        refined__data = refined_data(combined_str) 
        #st.write(refined__data)
        result =  generated_answer(query,refined__data)
        st.write(result)

