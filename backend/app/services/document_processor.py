"""
Document parsing and chunking service
Supports PDF / Word / Markdown / TXT formats
"""

import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.config import config


class DocumentProcessor:
    """Document processor"""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        self.chunk_size = chunk_size or config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or config.CHUNK_OVERLAP
        
        # Document loader mapping
        self.loaders = {
            ".pdf": PyPDFLoader,
            ".docx": Docx2txtLoader,
            ".txt": TextLoader,
            ".md": TextLoader,
            ".markdown": TextLoader,
        }
        # .doc old format requires antiword or textract, may not be available in Docker slim, skip for now
    
    def get_loader(self, file_path: str):
        """Get loader based on file extension"""
        ext = Path(file_path).suffix.lower()
        loader_class = self.loaders.get(ext)
        
        if not loader_class:
            raise ValueError(f"Unsupported file format: {ext}")
        
        # TXT/MD needs to specify encoding
        if ext in [".txt", ".md", ".markdown"]:
            return loader_class(file_path, encoding="utf-8")
        
        return loader_class(file_path)
    
    def load_document(self, file_path: str) -> List[Document]:
        """Load document (with error handling)"""
        import logging
        from http.client import IncompleteRead
        
        logger = logging.getLogger(__name__)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValueError(f"File is empty: {file_path}")
        
        try:
            loader = self.get_loader(file_path)
            documents = loader.load()
            
            # Verify document not empty
            if not documents:
                raise ValueError(f"Failed to extract content from file: {file_path}")
            
            # Verify document content
            for i, doc in enumerate(documents):
                if not doc.page_content or len(doc.page_content.strip()) == 0:
                    logger.warning(f"Document page {i} content is empty: {file_path}")
            
            # Add file path metadata
            for doc in documents:
                doc.metadata["source_file"] = file_path
                doc.metadata["file_name"] = Path(file_path).name
            
            logger.info(f"✅ Document loaded successfully: {file_path}, pages: {len(documents)}, size: {file_size} bytes")
            return documents
            
        except IncompleteRead as e:
            logger.error(f"❌ File read incomplete {file_path}: read {e.partial} bytes")
            raise ValueError(f"PDF file corrupted or incomplete: {file_path}")
        except Exception as e:
            logger.error(f"❌ Document load failed {file_path}: {type(e).__name__}: {e}")
            raise
    
    def split_documents(
        self,
        documents: List[Document],
        separators: List[str] = None
    ) -> List[Document]:
        """Split documents"""
        if separators is None:
            separators = ["\n\n", "\n", "。", ".", ", ", " "]
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=separators,
            length_function=len,
        )
        
        chunks = splitter.split_documents(documents)
        
        # Add chunk index
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
        
        return chunks
    
    def process_file(
        self,
        file_path: str,
        separators: List[str] = None
    ) -> List[Document]:
        """Process single file: load + split"""
        documents = self.load_document(file_path)
        chunks = self.split_documents(documents, separators)
        return chunks
    
    def process_directory(
        self,
        directory: str,
        recursive: bool = True
    ) -> List[Document]:
        """Process all documents in directory"""
        all_chunks = []
        
        for root, dirs, files in os.walk(directory):
            if not recursive:
                dirs.clear()  # Do not recurse into subdirectories
            
            for file in files:
                file_path = os.path.join(root, file)
                ext = Path(file_path).suffix.lower()
                
                if ext in self.loaders:
                    try:
                        chunks = self.process_file(file_path)
                        all_chunks.extend(chunks)
                        print(f"✅ Processing complete: {file} ({len(chunks)} chunks)")
                    except Exception as e:
                        print(f"❌ Processing failed: {file} - {e}")
        
        return all_chunks


# Singleton
document_processor = DocumentProcessor()
