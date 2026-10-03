
from dotenv import load_dotenv
load_dotenv()

import os
import re
import glob

from langchain_core.documents import Document
from langchain_community.document_loaders import PyMuPDFLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb
import uuid
from groq import Groq


# 1. Determine folder path
# Automatically handles Modal cloud vs local laptop
folder_path = "/root/PDFS" if os.path.exists("/root/PDFS") else "PDFS"


# 2. Data Loader
def load_all_pdfs():
    num_docs = 0
    all_docs = []

    for filename in os.listdir(folder_path):

        if filename.lower().endswith(".pdf"):

            pdf_path = os.path.join(
                folder_path,
                filename
            )

            loader = PyPDFLoader(pdf_path)
            doc = loader.load()

            all_docs.extend(doc)
            num_docs += 1

    print("total pdfs:", num_docs)
    print("total pages:", len(all_docs))

    return all_docs


# 3. Embedding Manager
class EmbeddingManager:

    def __init__(
        self,
        model_name="all-MiniLM-L6-v2"
    ):

        self.model_name = model_name

        print(
            "loading model....",
            self.model_name
        )

        self.model = SentenceTransformer(
            self.model_name
        )

        print(
            "embedding dimensions=",
            self.model.get_sentence_embedding_dimension()
        )

    def generate_embeddings(self, text):

        embeddings = self.model.encode(
            text,
            show_progress_bar=False
        )

        return embeddings


embedding_manager = EmbeddingManager()


# 4. Vector Store Manager
class VectorStoreManager:

    def __init__(
        self,
        persist_directory="data/vector_store",
        collection_name="northlight_docs_v5"
    ):

        self.collection_name = collection_name
        self.persist_directory = persist_directory

        self.collection = None
        self.client = None

        self._initialize_store()

    def _initialize_store(self):

        os.makedirs(
            self.persist_directory,
            exist_ok=True
        )

        self.client = chromadb.PersistentClient(
            path=self.persist_directory
        )

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "description":
                "vector store collection for pdf embeddings in RAG"
            }
        )

        print(
            "initialized vector store collection:",
            self.collection_name
        )


vector_store = VectorStoreManager()


# 5. Advanced Chunking & Indexing

fallback = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=150,
    separators=[
        "\n\n",
        "\n",
        ". ",
        " "
    ]
)


chunks = []


for path in sorted(
    glob.glob(
        os.path.join(
            folder_path,
            "*.pdf"
        )
    )
):

    pages = PyMuPDFLoader(path).load()

    full_text = "\n".join(
        p.page_content
        for p in pages
    )

    name = os.path.basename(path)

    sections = re.split(
        r"\n(?=\d+\. [A-Z])"
        r"|\n(?=Q: )"
        r"|\n(?=(?:Before Day 1|Day 1 Checklist|Week 1 Goals|Week 2 Goals|Key Contacts|30-60-90 Day Check-ins)\n)",
        full_text
    )

    i = 0

    for sec in sections:

        sec = sec.strip()

        if not sec:
            continue

        if len(sec) <= 800:

            parts = [sec]

        else:

            parts = fallback.split_text(sec)

        for part in parts:

            chunks.append(
                (
                    f"{name}_{i}",
                    part,
                    {
                        "source": name,
                        "chunk_index": i
                    }
                )
            )

            i += 1


# Add embeddings to ChromaDB only if collection is empty
if (
    vector_store.collection.count() == 0
    and chunks
):

    ids = [
        c[0]
        for c in chunks
    ]

    texts = [
        c[1]
        for c in chunks
    ]

    metas = [
        c[2]
        for c in chunks
    ]

    embs = embedding_manager.generate_embeddings(
        texts
    )

    vector_store.collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=[
            e.tolist()
            for e in embs
        ],
        metadatas=metas
    )

    print(
        "indexed",
        len(chunks),
        "chunks into vector store"
    )


# 6. RAG Retriever
class RAGRetriever:

    def __init__(
        self,
        embedding_manager,
        vector_store
    ):

        self.embedding_manager = embedding_manager
        self.vector_store = vector_store

    def retrieve(
        self,
        query,
        top_k=5,
        score_threshold=-10
    ):

        # Generate embedding for the user's question.
        # SentenceTransformer returns shape:
        # [1, 384]
        #
        # [0] extracts the single 384-dimensional
        # embedding for this query.

        query_embedding = (
            self.embedding_manager
            .generate_embeddings([query])[0]
        )

        # Chroma expects:
        # [[384 numbers]]
        #
        # Therefore we wrap the single embedding
        # inside a list.

        results = self.vector_store.collection.query(
            query_embeddings=[
                query_embedding.tolist()
            ],
            n_results=top_k
        )

        retrieved_docs = []

        if (
            results["documents"]
            and results["documents"][0]
        ):

            ids = results["ids"][0]

            metadatas = results["metadatas"][0]

            documents = results["documents"][0]

            distances = results["distances"][0]

            for i, (
                doc_id,
                metadata,
                document,
                distance
            ) in enumerate(
                zip(
                    ids,
                    metadatas,
                    documents,
                    distances
                )
            ):

                similarity_score = (
                    1 - distance / 2
                )

                if (
                    similarity_score
                    >= score_threshold
                ):

                    retrieved_docs.append(
                        {
                            "id": doc_id,
                            "document": document,
                            "metadata": metadata,
                            "distance": distance,
                            "similarity_score": similarity_score,
                            "rank": i + 1
                        }
                    )

        return retrieved_docs


rag_retriever = RAGRetriever(
    embedding_manager,
    vector_store
)


# 7. Groq LLM Integration

client_llm = Groq(
    api_key=os.getenv(
        "GROQ_API_KEY"
    )
)


# 8. System Prompt

SYSTEM_PROMPT = """You are an HR assistant for Northlight Analytics.

Answer ONLY using the provided context chunks.

Rules:
- Cite the source file name for each fact, like (05_Remote_Tools_and_Communication_Guide.pdf).
- If two sources give different answers to the same question, do NOT pick one. Start with "The documents disagree:" and list what each source says, with its file name.
- Include every relevant number, amount, and deadline from the context, not just the first one.
- If the context does not contain the answer, say "I don't have that information in the documents." Do not guess.
- If the context is ambiguous, state the ambiguity and give the number exactly as written. Do NOT calculate or assume a total the documents don't state.
- Keep answers short and direct.
"""


# 9. Answer Function

def answer(
    question,
    top_k=5
):

    # Retrieve relevant chunks
    results = rag_retriever.retrieve(
        question,
        top_k=top_k,
        score_threshold=-10
    )

    # Build context for the LLM
    context = "\n\n".join(
        f"[Source: {r['metadata']['source']}]\n"
        f"{r['document']}"
        for r in results
    )

    # Send context + question to Groq
    response = client_llm.chat.completions.create(

        model="openai/gpt-oss-120b",

        temperature=0,

        max_tokens=1000,

        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"Question: {question}"
                )
            }
        ]
    )

    return (
        response.choices[0].message.content,
        results
    )
