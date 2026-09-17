from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from langchain_mistralai import MistralAIEmbeddings
import os
from dotenv import load_dotenv

load_dotenv()

pc = Pinecone(
    api_key=os.getenv("PINECONE_API_KEY")
)

embeddings = MistralAIEmbeddings(
    model="mistral-embed",
    api_key=os.getenv("MISTRAL_API_KEY")
)

vector_store = PineconeVectorStore(
    index_name="ecommerce-policies",
    embedding=embeddings
)