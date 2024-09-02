# import os

# from langchain_community.document_loaders import PyPDFDirectoryLoader, PyPDFLoader
# from langchain_community.embeddings import OpenAIEmbeddings
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_community.vectorstores import Pinecone as pine
# from pinecone import Pinecone
# from dotenv import load_dotenv

# load_dotenv()


# # initialize PineCone.
# pc = Pinecone(
#    api_key=os.getenv("PINECONE_API_KEY"),
#    environment=os.getenv("PINECONE_ENV"),
# )

# print(pc)


# # Function to put vector dataset in pinecone vector DB
# def ingest_docs():
#     INDEX_NAME = os.environ["INDEX_NAME"]
#     print(INDEX_NAME)
#     description = pc.describe_index(name=INDEX_NAME)
#     print(description.status)
#     try:
#         index = pc.Index(name=INDEX_NAME)
#         index.delete(delete_all=True)
#         print(f"All existing vectors deleted")
#     except Exception as e:
#         print(f"got error while deleting {e}")
#     description = pc.describe_index(name=INDEX_NAME)
#     print(description.status)
#     print("Loading Docs")
#     loader = PyPDFDirectoryLoader("/home/bhupendra.singh/Desktop/upi_poc/Education POC/education_data")
#     raw_documents = loader.load()
#     print(f"loaded {len(raw_documents) }documents")
#     text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=10)
#     documents = text_splitter.split_documents(documents=raw_documents)
#     print(f"Splitted into {len(documents)} chunks")

#     print(f"Going to add {len(documents)} to Pinecone")
#     embeddings = OpenAIEmbeddings()
#     pine.from_documents(documents, embeddings, index_name=INDEX_NAME)

#     print("****Loading to vectorestore done ***")


# # set Environment Variables and ingest Data on pinecone
# if __name__ == "__main__":
#     ingest_docs()

print("ingest.py")
