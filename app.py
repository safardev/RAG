import os
import re
from flask import Flask, request, jsonify
from google import genai
from werkzeug.utils import secure_filename
from pathlib import Path
from io import BytesIO
import fitz
from docx import Document
from dotenv import load_dotenv

# Load .env from the same directory as weather.py
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

GEMINI_KEY = os.getenv("GEMINI_API_KEY")

#Google LLM
llm = genai.Client(api_key=GEMINI_KEY)

app = Flask(__name__)

# Folder where uploaded files will be saved
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Maximum upload size: 16 MB
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

@app.route("/")
def home():
    return "Flask is running"

@app.route("/api")
def get_data():
    return jsonify({
        "message": "Hello from Flask!",
        "status": "success"
    })

# @app.route("/uploads",methods=["POST"])
# def upload_file():
#     file=request.files.get("file")

#     if file is None:
#         return jsonify({"error":"No file provides"}),400

#     if file.filename == "":
#         return jsonify({"error":"No file selcted"}), 400

#     fileName = secure_filename(file.filename)

#     if not fileName:
#         return jsonify({"error":"Invalid filename"}), 400

#     file.save(UPLOAD_FOLDER / fileName)

#     return jsonify({
#         "message": "File uploaded successfully",
#         "filename": fileName
#     }), 201

@app.route("/read-file", methods=["POST"])
def read_file():
    file = request.files.get("file")

    if file is None or file.filename == "":
        return jsonify({"error": "Please upload a file"}), 400

    extension = Path(file.filename).suffix.lower()
    file_bytes = file.read()

    try:
        # Read plain-text files
        if extension in [".txt", ".csv", ".json", ".md"]:
            try:
                content = file_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                content = file_bytes.decode("cp1252")

        # Extract text from PDF
        elif extension == ".pdf":
            pdf = fitz.open(stream=file_bytes, filetype="pdf")
            chunks = []

            for page in pdf:
                blocks = page.get_text("blocks", sort=True)

                for block in blocks:
                    text = block[4].strip()

                    # Split paragraphs when blank lines are present
                    paragraphs = re.split(r"\n\s*\n+", text)

                    for paragraph in paragraphs:
                        # Join wrapped lines within a paragraph
                        paragraph = re.sub(r"\s+", " ", paragraph).strip()

                        if paragraph:
                            chunks.append(paragraph)

            pdf.close()

            response = llm.models.generate_content(
                        model="gemini-3.5-flash-lite",
                        contents=f"""
                        Explain the following PDF text in simple language.
                        Keep the important points and use bullet points where appropriate.

                        PDF text:
                        {chunks[0]}
                        """
                    )

        # # Split text into a list
        #     content = [
        #     re.sub(r"\s+", " ", paragraph).strip()
        #     for paragraph in re.split(r"\n\s*\n+", raw_text.strip())
        #     if paragraph.strip()
        #     ]

        # Extract text from Word documents
        elif extension == ".docx":
            document = Document(BytesIO(file_bytes))
            content = "\n".join(
                paragraph.text
                for paragraph in document.paragraphs
            )

        else:
            return jsonify({
                "error": "Unsupported file type. Use TXT, CSV, JSON, MD, PDF, or DOCX."
            }), 415

        return jsonify({
            "filename": file.filename,
            "content": response.text
        }), 200

    except Exception:
        return jsonify({
            "error": "Unable to extract text from this file. Check that the file is valid and not corrupted."
        }), 400

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)