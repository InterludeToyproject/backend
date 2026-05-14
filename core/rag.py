import os
from pathlib import Path
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
REGULATIONS_DIR = BASE_DIR / "data" / "regulations"
VECTORSTORE_DIR = str(BASE_DIR / "vectorstore")

def load_documents():
    """규제문서 PDF 전체 로드"""
    docs = []
    pdf_files = list(REGULATIONS_DIR.glob("*.pdf"))
    
    print(f"📂 총 {len(pdf_files)}개 파일 발견")
    
    for pdf_path in pdf_files:
        print(f"  로딩 중: {pdf_path.name}")
        loader = PyMuPDFLoader(str(pdf_path))
        documents = loader.load()
        
        # 파일명을 메타데이터로 저장
        for doc in documents:
            doc.metadata["source_file"] = pdf_path.name
            doc.metadata["law_name"] = pdf_path.stem
        
        docs.extend(documents)
    
    print(f"✅ 총 {len(docs)} 페이지 로드 완료")
    return docs

def split_documents(docs):
    """청크 분할"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "제", "①", "②", "③", " ", ""]
    )
    
    chunks = splitter.split_documents(docs)
    print(f"✅ 총 {len(chunks)}개 청크 생성")
    return chunks

def build_vectorstore(chunks):
    """ChromaDB 벡터스토어 구축"""
    from langchain_chroma import Chroma
    from langchain_community.embeddings import HuggingFaceEmbeddings
    
    print("🔨 벡터스토어 구축 중...")
    
    # 임베딩 모델 (로컬, 무료)
    embeddings = HuggingFaceEmbeddings(
        model_name="jhgan/ko-sbert-nli",
        model_kwargs={"device": "cpu"}
    )
    
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=VECTORSTORE_DIR
    )
    
    print(f"✅ 벡터스토어 구축 완료: {VECTORSTORE_DIR}")
    return vectorstore

def load_vectorstore():
    """기존 벡터스토어 로드"""
    from langchain_community.embeddings import HuggingFaceEmbeddings
    
    embeddings = HuggingFaceEmbeddings(
        model_name="jhgan/ko-sbert-nli",
        model_kwargs={"device": "cpu"}
    )
    
    vectorstore = Chroma(
        persist_directory=VECTORSTORE_DIR,
        embedding_function=embeddings
    )
    
    return vectorstore

def search_regulations(query: str, k: int = 5):
    """규제 관련 조문 검색"""
    vectorstore = load_vectorstore()
    
    results = vectorstore.similarity_search_with_score(query, k=k)
    
    formatted = []
    for doc, score in results:
        formatted.append({
            "content": doc.page_content,
            "source": doc.metadata.get("source_file", ""),
            "law_name": doc.metadata.get("law_name", ""),
            "page": doc.metadata.get("page", 0),
            "score": round(score, 4)
        })
    
    return formatted

if __name__ == "__main__":
    # 최초 1회 실행: 벡터스토어 구축
    print("=== RegRadar RAG 파이프라인 구축 시작 ===")
    docs = load_documents()
    chunks = split_documents(docs)
    build_vectorstore(chunks)
    print("=== 구축 완료 ===")
