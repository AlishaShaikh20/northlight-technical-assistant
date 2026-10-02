

from langchain_core.documents import Document

sample_doc = Document(
    page_content="Hello World!",
    metadata={"source": "https://www.google.com"}
)

sample_doc

type(sample_doc)

# Data => Documents
import os
from langchain_community.document_loaders.pdf import PyPDFLoader

def load_all_pdfs():
    folder_path = "PDFS"
    num_docs = 0
    all_docs = []

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".pdf"):
            # complete file path
            pdf_path = os.path.join(folder_path, filename)

            loader = PyPDFLoader(pdf_path)
            doc = loader.load()

            all_docs.extend(doc)
            num_docs += 1

    print("total pdfs:", num_docs)
    print("total pages:", len(all_docs))
    return all_docs

all_pdf_documents = load_all_pdfs()

type(all_pdf_documents[1])


from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_docs(documents, chunk_size=500, chunk_overlap=50):

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = chunk_size,
        chunk_overlap = chunk_overlap
    )

    chunked_docs = text_splitter.split_documents(documents)
    return chunked_docs

chunks = split_docs(all_pdf_documents)

len(chunks)

from sentence_transformers import SentenceTransformer

class EmbeddingManager:
    def __init__(self, model_name="all-MiniLM-L6-v2"):

        self.model_name=model_name
        print("loading model....", self.model_name)
        self.model = SentenceTransformer(self.model_name)
        print("embedding dimensions=", self.model.get_sentence_embedding_dimension())


    def generate_embeddings(self, text):
        embeddings = self.model.encode(text, show_progress_bar=True)
        print("embeddings shape:", embeddings.shape)
        return embeddings

embedding_manager = EmbeddingManager()

import chromadb
import uuid

class VectorStoreManager:
    def __init__(self, persist_directory="data/vector_store", collection_name="pdf_documents"):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.collection = None
        self.client = None

        self._initialize_store()

    def _initialize_store(self):
        os.makedirs(self.persist_directory, exist_ok=True)

        # create a client
        self.client = chromadb.PersistentClient(path=self.persist_directory)

        # create the collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "vector store collection for pdf embeddings in RAG"}
        )

        print("initialized the vector store with collection:", self.collection_name)
        print("docs in collection:", self.collection.count())

    def add_documents(self, documents, embeddings):
        if len(documents) != len(embeddings):
            raise ValueError("num of documents does not match num of embeddings")


        # store => ids, embedding, document, metadata
        ids = []
        all_metadata = []
        documents_content = []
        embeddings_list = []

        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            doc_id = f"doc_{uuid.uuid4()}"
            ids.append(doc_id)

            metadata = dict(doc.metadata)
            metadata["doc_index"] = i
            metadata["content_length"] = len(doc.page_content)
            all_metadata.append(metadata)

            documents_content.append(doc.page_content)
            embeddings_list.append(embedding.tolist())

        if self.collection.count() == 0:
            self.collection.add(
                ids=ids,
                metadatas=all_metadata,
                documents=documents_content,
                embeddings=embeddings_list
            )
            print("total documents added in vector store=", len(documents_content))
        else:
            print("vector store already contains documents. Skipping re-indexing.")
        print("docs in collection:", self.collection.count())

vector_store = VectorStoreManager()

# data => documents => chunks => embeddings => store in vector store

texts = [doc.page_content for doc in chunks]

emebedding = embedding_manager.generate_embeddings(texts)

vector_store.add_documents(chunks, emebedding)

from sklearn.metrics.pairwise import cosine_similarity

class RAGRetriever:
    def __init__(self, embedding_manager, vector_store):
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store


    def retrieve(self, query, top_k=5, score_threshold=0.0):
        # query => embedding
        query_embeddings = self.embedding_manager.generate_embeddings([query])[0]

        # semantic search
        results = self.vector_store.collection.query(
            query_embeddings=[query_embeddings.tolist()],
            n_results=top_k
        )

        # cosine similarity
        retrieved_docs=[]

        if results["documents"] and results["documents"][0]:
            ids = results["ids"][0]
            metadatas = results["metadatas"][0]
            documents = results["documents"][0]
            distances = results["distances"][0]

            for i, (doc_id, metadata, document, distance) in enumerate(zip(ids, metadatas, documents, distances)):
                similarity_score = 1 - distance / 2

                if similarity_score >= score_threshold:
                    retrieved_docs.append({
                        "id": doc_id,
                        "document": document,
                        "metadata": metadata,
                        "distance": distance,
                        "similarity_score": similarity_score,
                        "rank" : i + 1
                    })

            print(f"retrieved {len(retrieved_docs)} documents")

        else:
            print("no documents found")

        return retrieved_docs

rag_retriever = RAGRetriever(embedding_manager, vector_store)

results = rag_retriever.retrieve(
    "Where do I request access to a new tool?",
    top_k=10,
    score_threshold=-10   # disable filtering
)
for r in results:
    print(r["rank"], round(r["distance"], 3), r["metadata"]["source"].split("/")[-1], "|", r["document"][:80].replace("\n", " "))

results = rag_retriever.retrieve(
    "What happens to my laptop and account when I leave the company?",
    top_k=5,
    score_threshold=-10
)
for r in results:
    print(r["rank"], round(r["distance"], 3), r["metadata"]["source"].split("/")[-1])
    print(r["document"])
    print("-----")

results = rag_retriever.retrieve(
    "How much is the home office stipend and when can I claim it?",
    top_k=5,
    score_threshold=-10
)
for r in results:
    print(r["rank"], round(r["distance"], 3), r["metadata"]["source"].split("/")[-1])
    print(r["document"])
    print("-----")

import re, glob, os
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

pdf_folder = "PDFS"
fallback = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150, separators=["\n\n", "\n", ". ", " "])

chunks = []  # list of (id, text, metadata)
for path in sorted(glob.glob(pdf_folder + "/*.pdf")):
    pages = PyMuPDFLoader(path).load()
    full_text = "\n".join(p.page_content for p in pages)   # keep this line
    full_text = re.sub(r"\nG\n", "\n- ", full_text)        # new line goes AFTER it
    name = os.path.basename(path)

    # split at numbered headings ("3. Home Office Stipend") and FAQ questions ("Q: ...")
    sections = re.split(
    r"\n(?=\d+\. [A-Z])|\n(?=Q: )|\n(?=(?:Before Day 1|Day 1 Checklist|Week 1 Goals|Week 2 Goals|Key Contacts|30-60-90 Day Check-ins)\n)",
    full_text
)
    i = 0
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        parts = [sec] if len(sec) <= 800 else fallback.split_text(sec)
        for part in parts:
            chunks.append((f"{name}_{i}", part, {"source": name, "chunk_index": i}))
            i += 1

print("total chunks:", len(chunks))

vector_store.collection = vector_store.client.get_or_create_collection(name="northlight_docs_v5")
print(vector_store.collection.count())   # should print 0

ids   = [c[0] for c in chunks]
texts = [c[1] for c in chunks]
metas = [c[2] for c in chunks]

embs = embedding_manager.generate_embeddings(texts)

vector_store.collection.upsert(
    ids=ids,
    documents=texts,
    embeddings=[e.tolist() for e in embs],
    metadatas=metas
)
print(len(chunks), vector_store.collection.count())   # both numbers must match

rag_retriever = RAGRetriever(embedding_manager, vector_store)

rag_retriever = RAGRetriever(embedding_manager, vector_store)

queries = [
    "Where do I request access to a new tool?",
    "What happens to my laptop and account when I leave the company?",
    "How much is the home office stipend and when can I claim it?",
]
for q in queries:
    print("=" * 60)
    print("QUERY:", q)
    results = rag_retriever.retrieve(q, top_k=5, score_threshold=-10)
    for r in results:
        print(r["rank"], round(r["distance"], 3), r["metadata"]["source"], "|", r["document"][:70].replace("\n", " "))


from groq import Groq

client_llm = Groq(api_key=os.getenv("GROQ_API_KEY"))
print("key loaded")

SYSTEM_PROMPT = """You are an HR assistant for Northlight Analytics.
Answer ONLY using the provided context chunks.
Rules:
- Cite the source file name for each fact, like (05_Remote_Tools_and_Communication_Guide.pdf).
- If two sources give different answers to the same question, do NOT pick one. Start with "The documents disagree:" and list what each source says, with its file name.
- Include every relevant number, amount, and deadline from the context, not just the first one.
- If the context does not contain the answer, say "I don't have that information in the documents." Do not guess.
- If the context is ambiguous (for example, it is unclear whether a price is per person or in total), state the ambiguity and give the number exactly as written. Do NOT calculate or assume a total the documents don't state.
- Keep answers short and direct."""

def answer(question, top_k=5):
    results = rag_retriever.retrieve(question, top_k=top_k, score_threshold=-10)

    context = "\n\n".join(
        f"[Source: {r['metadata']['source']}]\n{r['document']}" for r in results
    )

    response = client_llm.chat.completions.create(
        model="openai/gpt-oss-120b",
        temperature=0,
        max_tokens=1000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    return response.choices[0].message.content, results

for q in ["I'm on the PPO with a spouse and two kids, what's my monthly cost?"]:
    print("Q:", q)
    text, _ = answer(q)
    print("A:", text)


