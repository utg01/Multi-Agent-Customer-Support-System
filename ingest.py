from pinecone import Pinecone, ServerlessSpec
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_pinecone import PineconeVectorStore
from langchain_mistralai import MistralAIEmbeddings

import os
from dotenv import load_dotenv

load_dotenv()

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)

pdf_files = [
    "brightcart-app-platform-faq.pdf",
    "brightcart-coupon-discount-policy.pdf",
    "brightcart-order-cancellation-policy.pdf",
    "brightcart-refund-policy.pdf",
    "brightcart-return-policy.pdf",
    "brightcart-shipping-delivery-policy.pdf"
]



INDEX_NAME = "ecommerce-policies"

pc = Pinecone(
    api_key=os.getenv("PINECONE_API_KEY")
)

# Create index only if it doesn't already exist
if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=1024,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )



def create_docs(filename: str):
    loader = PyPDFLoader(f"Documents/{filename}")
    documents = loader.load()
    return splitter.split_documents(documents)


docs = []

for filename in pdf_files:
    docs += create_docs(filename)


embeddings = MistralAIEmbeddings(
    model="mistral-embed",
    api_key=os.getenv("MISTRAL_API_KEY")
)

vector_store = PineconeVectorStore.from_documents(
    documents=docs,
    embedding=embeddings,
    index_name="ecommerce-policies"
)

print(f"Successfully ingested {len(docs)} chunks.")