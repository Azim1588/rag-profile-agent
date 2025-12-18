import asyncio
from typing import List
from io import BytesIO
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pypdf import PdfReader
import docx


class DocumentProcessor:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF"""
        # PdfReader needs a file-like object that supports seeking
        pdf_file = BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    
    def extract_text_from_docx(self, file_bytes: bytes) -> str:
        """Extract text from DOCX"""
        # python-docx needs a file-like object that supports seeking
        docx_file = BytesIO(file_bytes)
        doc = docx.Document(docx_file)
        return "\n".join([para.text for para in doc.paragraphs])
    
    def chunk_text(self, text: str) -> List[str]:
        """Split text into chunks for better RAG performance"""
        return self.text_splitter.split_text(text)
    
    async def process_document(
        self,
        filename: str,
        file_bytes: bytes
    ) -> List[dict]:
        """Process document and return chunks with metadata"""
        # Extract text based on file type
        if filename.endswith('.pdf'):
            text = self.extract_text_from_pdf(file_bytes)
        elif filename.endswith('.docx'):
            text = self.extract_text_from_docx(file_bytes)
        else:
            text = file_bytes.decode('utf-8')
        
        # Chunk text
        chunks = self.chunk_text(text)
        
        # Create chunk documents with metadata
        documents = []
        for i, chunk in enumerate(chunks):
            documents.append({
                "filename": filename,
                "content": chunk,
                "metadata": {
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "source": filename
                }
            })
        
        return documents
