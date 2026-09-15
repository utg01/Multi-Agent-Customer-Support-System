from pinecone import Pinecone,ServerlessSpec
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_pinecone import PineconeVectorStore
from langchain_mistralai import MistralAIEmbeddings
import os
from dotenv import load_dotenv

load_dotenv()
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

"""pc.create_index(
    name="ecommerce-policies",
    dimension=1024,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
)"""

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

def create_docs(filename: str):
    loader = PyPDFLoader(f"Documents/{filename}")
    documents = loader.load()
    chunks = splitter.split_documents(documents)
    return chunks

docs = []

pdf_files = [
    "brightcart-app-platform-faq.pdf",
    "brightcart-coupon-discount-policy.pdf",
    "brightcart-order-cancellation-policy.pdf",
    "brightcart-refund-policy.pdf",
    "brightcart-return-policy.pdf",
    "brightcart-shipping-delivery-policy.pdf"
]

for i in pdf_files:
    docs += create_docs(i)

embeddings = MistralAIEmbeddings(
    model='mistral-embed',
    api_key=os.getenv("MISTRAL_API_KEY")
)

vector_store = PineconeVectorStore.from_documents(
    documents=docs,
    embedding=embeddings,
    index_name='ecommerce-policies'
)