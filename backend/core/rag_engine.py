"""
RAG engine: retrieve relevant tyre records then generate with GPT-4o-mini.
Supports multi-turn conversation history.
"""
import os
from typing import Generator, List, Optional

from openai import OpenAI

from .data_loader import get_models_for_brand, get_unique_brands
from .vector_store import build_vector_store, query_collection

SYSTEM_PROMPT = """You are a CEAT Tyre advisor strictly limited to recommending tyres for Indian 2-wheelers. You only answer questions about CEAT tyres, motorcycle tyre fitments, SKUs, and tyre specifications based on the data provided to you.

If the user asks anything outside of tyres or motorcycles — general knowledge, personal questions, geography, sports, or anything unrelated — politely decline and redirect. Say something like "I'm only set up to help with CEAT tyre recommendations for your bike — what motorcycle are you riding?"

You talk like a knowledgeable friend helping someone pick the right tyre — warm, natural, conversational.

Default response rules (unless the user asks for more detail):
- NEVER use markdown lists, bullet points, numbered lists, or headers. Write everything as natural flowing prose — like a friend explaining it verbally.
- Recommend tyres using the complete tyre name exactly as it appears in the data. Always wrap tyre names in markdown bold, e.g. **2.75-18 SECURA ZOOM F TT**, **130/70-17 ZOOM XL TL**. Do NOT shorten it to just the brand series.
- Do NOT mention SKU codes, material codes, or numeric identifiers unless explicitly asked.
- For a single model: say something like "For the front you'll want the **X**, and for the rear go with the **Y**."
- For multiple variants: write it as a natural paragraph, e.g. "The Pulsar 150cc runs the **X** up front and **Y** at the back. The NS 200 is a bit different — it uses the **A** in front and **B** at the rear." Keep it conversational, not a list.
- Always mention both front and rear tyres. If only one position is in the retrieved data, say something like "I only have the rear tyre on record for this model — go with the **X**. For the front, please check with your dealer."
- If the exact model isn't in the data, recommend the closest match and mention it's the closest fit.

When the user specifically asks for the SKU, material code, or product code:
- Provide the SKU as a plain integer wrapped in bold, e.g. **113264**.
- You can say something like "The SKU for that tyre is **113264**."

You have memory of the conversation. For follow-up questions (e.g. "what's the SKU?", "which one is tubeless?",
"tell me more about the rear tyre"), refer back to the tyres you already recommended — do not ask the user
to repeat themselves.

Always recommend from the retrieved context only. Never invent tyre names or codes.
"""

MODEL = "gpt-4o-mini"


class TyreRAG:
    def __init__(self, excel_path: str = None, quiet: bool = False):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set.")

        if not quiet:
            print("Loading tyre data and building vector index…")
        self._collection, self._records = build_vector_store(excel_path)
        self._client = OpenAI(api_key=api_key)
        if not quiet:
            print(f"Vector store ready — {self._collection.count()} records indexed.")

    @property
    def record_count(self) -> int:
        return self._collection.count()

    # ------------------------------------------------------------------
    # Brand / model catalogue helpers
    # ------------------------------------------------------------------
    def get_brands(self) -> List[str]:
        return get_unique_brands(self._records)

    def get_models(self, brand: str) -> List[str]:
        return get_models_for_brand(self._records, brand)

    # ------------------------------------------------------------------
    # Retrieve
    # For follow-up questions we augment the query with the last assistant
    # reply so that "what's the SKU?" still fetches the right tyre records.
    # ------------------------------------------------------------------
    def retrieve(
        self,
        query: str,
        history: Optional[List[dict]] = None,
        n_results: int = 14,
    ) -> List[dict]:
        retrieval_query = self._augment_query(query, history)
        return query_collection(self._collection, retrieval_query, n_results=n_results)

    # ------------------------------------------------------------------
    # Sync — used by Telegram bot
    # ------------------------------------------------------------------
    def recommend(self, query: str, history: Optional[List[dict]] = None) -> str:
        context = self.retrieve(query, history)
        messages = self._build_messages(query, context, history)
        response = self._client.chat.completions.create(
            model=MODEL,
            max_tokens=1024,
            messages=messages,
        )
        return response.choices[0].message.content

    # ------------------------------------------------------------------
    # Streaming — used by web API and CLI
    # ------------------------------------------------------------------
    def recommend_stream(
        self, query: str, history: Optional[List[dict]] = None
    ) -> Generator[str, None, None]:
        context = self.retrieve(query, history)
        yield from self.recommend_stream_from_context(query, context, history)

    def recommend_stream_from_context(
        self,
        query: str,
        context: List[dict],
        history: Optional[List[dict]] = None,
    ) -> Generator[str, None, None]:
        messages = self._build_messages(query, context, history)
        stream = self._client.chat.completions.create(
            model=MODEL,
            max_tokens=1024,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _augment_query(self, query: str, history: Optional[List[dict]]) -> str:
        """
        For follow-up questions that don't mention a vehicle, append the last
        assistant reply so the vector search still finds the right records.
        E.g. "what's the SKU?" + last reply → retrieves the correct tyre docs.
        """
        if not history:
            return query
        # Find the most recent assistant message
        for msg in reversed(history):
            if msg["role"] == "assistant":
                # Truncate to avoid bloating the embedding
                snippet = msg["content"][:400]
                return f"{query} {snippet}"
        return query

    def _build_messages(
        self,
        query: str,
        context: List[dict],
        history: Optional[List[dict]] = None,
    ) -> list:
        context_text = "\n\n---\n\n".join(hit["document"] for hit in context)
        user_content = (
            f"{query}\n\n"
            f"[Relevant tyre data from database]\n{context_text}"
        )
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_content})
        return messages
