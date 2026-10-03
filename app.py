from flask import Flask, render_template, request, jsonify
import os
from pathlib import Path
from langchain_community.document_loaders import PyMuPDFLoader

from rag_chatbot_pipeline import answer
from dotenv import load_dotenv
load_dotenv()  # This loads variables from your .env file into os.environ

import os
from groq import Groq

# Now this will successfully find your GROQ_API_KEY from the .env file
client_llm = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "").strip()

    if not question:
        return jsonify({
            "type": "none",
            "answer": "Please enter a question.",
            "sources": []
        })

    try:
        response, results = answer(question, top_k=5)

        sources = []

        for r in results:
            sources.append({
                "file": r["metadata"]["source"],
                "text": r["document"],
                "score": r["similarity_score"]
            })

        if response.startswith("The documents disagree:"):
            result_type = "warn"
        elif response.startswith("I don't have that information"):
            result_type = "none"
        else:
            result_type = "answer"

        return jsonify({
            "type": result_type,
            "answer": response,
            "sources": sources
        })

    except Exception as e:
        print("ERROR:", e)

        return jsonify({
            "type": "none",
            "answer": "Something went wrong while processing your question.",
            "sources": []
        }), 500


@app.route("/docs")
def docs():
    pdf_folder = Path("PDFS")
    documents = {}

    for pdf_path in sorted(pdf_folder.glob("*.pdf")):
        try:
            pages = PyMuPDFLoader(str(pdf_path)).load()
            text = "\n\n".join(page.page_content for page in pages)

            documents[pdf_path.name] = {
                "title": pdf_path.stem.replace("_", " "),
                "text": text
            }

        except Exception as e:
            print(f"Could not load {pdf_path.name}: {e}")

    return jsonify(documents)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)