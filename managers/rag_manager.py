"""
RAG 검색 매니저 (메모리 최적화 + 토크나이저 이슈 수정 버전)
벡터DB에서 사용자 질문과 관련된 지식을 검색합니다.
"""

import os
import pickle
import torch
import faiss
import numpy as np
from transformers import XLMRobertaModel, AutoTokenizer
import torch.nn.functional as F
from typing import List, Tuple

class RAGManager:
    """파인튜닝된 KURE-v1 + FAISS 벡터DB로 지식 검색"""
    
    def __init__(
        self,
        model_path: str = "assets/models/KURE-v1-yuhwa-final",
        vectordb_path: str = "assets/database/vectordb"
    ):
        print("[RAG] 초기화 중...")
        
        # 1. CPU 강제 사용 (메모리 효율)
        self.device = 'cpu'
        print(f"[RAG] Device: {self.device}")
        
        # 2. Tokenizer 로드 (Regex 오류 수정 적용)
        print("[RAG] Tokenizer 로딩...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                fix_mistral_regex=True  # [수정] 토크나이저 정규식 오류 방지 플래그
            )
        except TypeError:
            # 만약 모델이 이 플래그를 지원하지 않는 구형/다른 아키텍처일 경우 대비
            print("[RAG] fix_mistral_regex 옵션이 필요 없거나 지원되지 않아 제외하고 로드합니다.")
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        
        # 3. Model 로드 (메모리 최적화 적용)
        print("[RAG] Model 로딩 중 (from_pretrained)...")
        try:
            # safetensors를 사용하여 메모리 효율적으로 로드
            self.model = XLMRobertaModel.from_pretrained(
                model_path,
                use_safetensors=True,
                local_files_only=True
            )
        except Exception as e:
            print(f"[RAG] 모델 로딩 실패: {e}")
            raise e
        
        self.model = self.model.to(self.device)
        self.model.eval()
        
        print("[RAG] 모델 로드 완료")
        
        # 4. 벡터DB 로드
        print("[RAG] 벡터DB 로딩...")
        index_file = os.path.join(vectordb_path, "yuhwa.index")
        chunks_file = os.path.join(vectordb_path, "chunks.pkl")
        metadata_file = os.path.join(vectordb_path, "metadata.pkl")
        
        if not os.path.exists(index_file) or not os.path.exists(chunks_file):
             raise FileNotFoundError(f"벡터 DB 파일이 경로에 없습니다: {vectordb_path}")

        self.index = faiss.read_index(index_file)
        
        with open(chunks_file, 'rb') as f:
            self.chunks = pickle.load(f)
        
        with open(metadata_file, 'rb') as f:
            self.metadata = pickle.load(f)
        
        print(f"[RAG] 완료: {len(self.chunks)}개 청크")
    
    def _mean_pooling(self, model_output, attention_mask):
        """Mean pooling for embeddings"""
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    
    def _encode_text(self, text: str) -> np.ndarray:
        """텍스트를 벡터로 변환"""
        encoded_input = self.tokenizer(
            [text],
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors='pt'
        ).to(self.device)
        
        with torch.no_grad():
            model_output = self.model(**encoded_input)
        
        embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
        embeddings = F.normalize(embeddings, p=2, dim=1)
        
        return embeddings.cpu().numpy().astype('float32')
    
    def search(self, query: str, top_k: int = 3) -> List[Tuple[str, float, dict]]:
        """
        질문과 관련된 지식을 검색합니다.
        
        Returns: [(청크 텍스트, 유사도, 메타데이터), ...]
        """
        # 쿼리 임베딩
        query_vec = self._encode_text(query)
        
        # FAISS 검색
        distances, indices = self.index.search(query_vec, top_k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
                
            results.append((
                self.chunks[idx],
                float(dist),
                self.metadata[idx]
            ))
        
        return results
    
    def format_for_prompt(self, search_results: List[Tuple[str, float, dict]]) -> str:
        """검색 결과를 프롬프트 형식으로 변환"""
        if not search_results:
            return ""
        
        formatted = "### 참고 지식:\n"
        for i, (chunk, score, meta) in enumerate(search_results, 1):
            formatted += f"\n[{i}] (유사도: {score:.3f})\n{chunk}\n"
        
        return formatted