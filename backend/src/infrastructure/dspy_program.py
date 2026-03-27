import dspy
import asyncio
from typing import List
from src.application.rag_service import RAGService
from src.domain.models import SearchQuery

class WinnerSelectionSignature(dspy.Signature):
    """
    Task: Select the best unique sources from the list that are most relevant to the query.
    Criteria:
    1. Relevance: The source must directly address the specific search query.
    2. Authority: Prefer official business sites, government portals, or trusted aggregators (Maps, 2GIS, etc.).
    3. Verifiability: Look for physical markers in snippets (addresses, phone numbers, contact info).
    4. Diversity: Avoid duplicate content from different URLs.
    """
    query = dspy.InputField()
    candidates = dspy.InputField(desc="Numbered list containing candidate Title, URL, and a Snippet of content.")
    thought = dspy.OutputField(desc="Reasoning about the relevance and authority of the candidates.")
    winner_indices = dspy.OutputField(desc="Comma-separated list of indices of the best sources (e.g. 0, 3, 1, 7, 2, 5)")

class RAGModule(dspy.Module):
    def __init__(self, rag_service: RAGService, lm=None):
        super().__init__()
        self.rag_service = rag_service
        self.lm = lm
        # Предиктор для оптимизации
        self.select_winners = dspy.ChainOfThought(WinnerSelectionSignature)
        self.rag_service.opt_winner_selector = self.select_winners

    def forward(self, query: str, chunk_size: int = None, chunk_overlap: int = None):
        import nest_asyncio
        import asyncio
        nest_asyncio.apply()
        
        # Apply adaptive chunking if provided
        if chunk_size is not None:
            self.rag_service.chunker.chunk_size = chunk_size
        if chunk_overlap is not None:
            self.rag_service.chunker.overlap = chunk_overlap

        query_data = SearchQuery(query=query)
        try:
            loop = asyncio.get_event_loop()
            
            # Используем context manager вместо глобального configure
            ctx = dspy.context(lm=self.lm) if hasattr(dspy, 'context') else dspy.settings.context(lm=self.lm)
            
            if self.lm:
                with ctx:
                    response = loop.run_until_complete(self.rag_service.ask(query_data))
            else:
                response = loop.run_until_complete(self.rag_service.ask(query_data))
            
            urls = [s.url for s in response.sources]
            urls_str = ", ".join(urls)
            return dspy.Prediction(urls=urls_str)
        except Exception as e:
            import sys
            import traceback
            sys.stderr.write(f"[DEBUG] RAGModule Forward Error: {e}\n")
            traceback.print_exc()
            return dspy.Prediction(urls="")

def overlap_metric(example, pred, trace=None):
    def normalize(u):
        if not u: return ""
        # Lenient normalization
        u = u.split('?')[0].split('#')[0].strip('/').lower()
        prefixes = ["https://", "http://", "www."]
        for p in prefixes:
            if u.startswith(p):
                u = u[len(p):]
        return u

    gold_urls = [normalize(u) for u in example.expected_urls if u]
    pred_urls_str = getattr(pred, "urls", "") or ""
    pred_urls = [normalize(u) for u in pred_urls_str.split(", ") if u]
    
    if not gold_urls:
        return 0.0
        
    score = 0
    for g_url in gold_urls:
        # Префиксное совпадение: если предсказанный URL начинается с эталонного
        matched = False
        for p_url in pred_urls:
            if p_url == g_url or p_url.startswith(g_url + '/'):
                matched = True
                break
        if matched:
            score += 1
            
    return score / len(gold_urls)
