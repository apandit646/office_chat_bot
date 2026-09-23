"""Load PDFs from the data folder, split them into chunks and store them in ChromaDB.

Run once (and again whenever the PDFs change):
    python -m app.ingest
"""
import shutil

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app import config


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=config.EMBEDDING_MODEL, google_api_key=config.require_api_key()
    )


def ingest() -> int:
    pdfs = sorted(config.DATA_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDF files found in {config.DATA_DIR}. Add your policy PDFs there.")

    docs = []
    for pdf in pdfs:
        pages = [
            Document(page_content=text, metadata={"source": pdf.name, "page": i})
            for i, page in enumerate(PdfReader(pdf).pages)
            if (text := page.extract_text() or "").strip()
        ]
        docs.extend(pages)
        print(f"Loaded {len(pages):>3} pages from {pdf.name}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)

    # Rebuild from scratch so re-running doesn't create duplicate chunks
    if config.CHROMA_DIR.exists():
        shutil.rmtree(config.CHROMA_DIR)

    Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        collection_name=config.COLLECTION_NAME,
        persist_directory=str(config.CHROMA_DIR),
    )
    print(f"Indexed {len(docs)} pages as {len(chunks)} chunks into {config.CHROMA_DIR}")
    return len(chunks)


if __name__ == "__main__":
    ingest()
