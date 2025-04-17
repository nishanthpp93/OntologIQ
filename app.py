import json
import os
import flask
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, Response, stream_with_context, session
from llama_index.core import GPTVectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.readers.file.base import SimpleDirectoryReader

from pdf_scraper import scrape_and_download_pdfs
from support_functions import get_completion
from openai import OpenAI
import markdown2

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

client = OpenAI()

# Paths and Index setup
documents_folder = "documents"
vector_index_path = "nccn_vectors"

if Path(vector_index_path).exists():
    storage_context = StorageContext.from_defaults(persist_dir=vector_index_path)
    llama_index = load_index_from_storage(storage_context)
# else:
#     if not Path(documents_folder).exists():
#         scrape_and_download_pdfs(documents_folder)
#         documents = SimpleDirectoryReader(documents_folder).load_data()
#         parser = SimpleNodeParser()
#         nodes = parser.get_nodes_from_documents(documents)
#         llama_index = GPTVectorStoreIndex.from_documents(documents)
#         llama_index.storage_context.persist(persist_dir=vector_index_path)
#     else:
#         documents = SimpleDirectoryReader(documents_folder).load_data()
#         parser = SimpleNodeParser()
#         nodes = parser.get_nodes_from_documents(documents)

# Configure markdown with extras
markdown_converter = markdown2.Markdown(extras=[
    "fenced-code-blocks",
    "tables",
    "break-on-newline",
    "code-friendly"
])

@app.template_filter('markdown')
def markdown_filter(text):
    """
    Custom markdown filter that preserves the original markdown when stored
    but renders it properly when displayed
    """
    if not text:
        return ""
    try:
        # Use markdown2 with configured extras
        return markdown_converter.convert(text)
    except Exception as e:
        app.logger.error(f"Markdown conversion error: {str(e)}")
        return text

# Global state
conversation_history = []
last_sources = []
past_conversations = []

def generate_6_word_summary(conversation):
    summary_prompt = "Summarize this conversation in EXACTLY 6 words:\n\n"
    for msg in conversation:
        role_str = "User" if msg["role"] == "user" else "Assistant"
        # Strip markdown formatting for summary generation
        content = msg['content']
        summary_prompt += f"{role_str}: {content}\n"

    summary_prompt += "\nRemember: EXACTLY 6 words only."
    messages = [{"role": "user", "content": summary_prompt}]
    six_word_summary = get_completion(messages, client).strip()
    return six_word_summary

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about_us')
def about_us():
    return render_template('about_us.html')

@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms_of_service')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/chat')
def open_ai_chatbot():
    return render_template(
        "chat.html",
        conversation_history=conversation_history,
        sources=last_sources,
        past_conversations=past_conversations
    )

@app.route('/load_conversation/<int:conv_id>')
def load_conversation(conv_id):
    global conversation_history, last_sources, past_conversations

    for conv in past_conversations:
        if conv["id"] == conv_id:
            # Ensure we're storing the raw markdown
            conversation_history = conv["history"][:]
            last_sources = conv.get("sources", [])
            break

    return redirect(url_for('open_ai_chatbot'))

@app.route('/new_conversation', methods=['POST'])
def new_conversation():
    global conversation_history, last_sources, past_conversations

    if conversation_history:
        summary_text = generate_6_word_summary(conversation_history)
        new_id = len(past_conversations) + 1

        past_conversations.append({
            "id": new_id,
            "history": conversation_history.copy(),  # Store the raw markdown
            "summary": summary_text,
            "sources": last_sources.copy()
        })

    conversation_history = []
    last_sources = []
    return redirect(url_for('open_ai_chatbot'))

@app.route('/submit', methods=['GET'])
def process_question():
    global conversation_history, last_sources

    question = request.args.get("question", "").strip()
    if not question:
        return "No question provided", 400

    def generate():
        try:
            conversation_history.append({"role": "user", "content": question})
            yield "data: " + json.dumps({"type": "user", "content": question}) + "\n\n"

            query_engine = llama_index.as_query_engine(similarity_top_k=3)
            retrieved_context = query_engine.retrieve(question)

            new_sources = []
            for node_with_score in retrieved_context:
                metadata = node_with_score.node.metadata
                page_label = metadata.get("page_label", "Unknown Page")
                file_name = metadata.get("file_name", "Unknown File")
                title_name = file_name.replace("-", " ").title()[:-4]
                link = f"https://www.nccn.org/patients/guidelines/content/PDF/{file_name}"
                new_sources.append({"page_label": page_label, "link": link, "file_name": title_name})

            last_sources = new_sources
            yield "data: " + json.dumps({"type": "sources", "content": new_sources}) + "\n\n"

            # Build message history for context
            full_message = []
            for msg in conversation_history:
                full_message.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

            system_prompt = (
                f"Use the following retrieved context to answer the user's last question:\n"
                f"{retrieved_context}\n"
                f"The user's last question: {question}\n\n"
                f"Format your response using markdown syntax for any lists, code blocks, or emphasis."
            )
            full_message.append({"role": "system", "content": system_prompt})

            # Stream the response
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=full_message,
                stream=True
            )

            collected_messages = []
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    collected_messages.append(content)
                    # Send the raw markdown content
                    yield "data: " + json.dumps({"type": "assistant", "content": content}) + "\n\n"

            # Store final response in conversation history (raw markdown)
            final_response = "".join(collected_messages)
            conversation_history.append({
                "role": "assistant",
                "content": final_response
            })

        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            conversation_history.append({"role": "assistant", "content": error_msg})
            last_sources = []
            yield "data: " + json.dumps({"type": "error", "content": error_msg}) + "\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=False)
