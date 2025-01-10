
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
import os
import shutil
from tinydb import TinyDB, Query
from datetime import datetime
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
import json

# Import RAG components
from langchain_ollama.llms import OllamaLLM
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.chains import RetrievalQA
from fpdf import FPDF

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['FOLDERS'] = 'folders'
db = TinyDB('data/query_history.json')
# Create folders if they do not exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['FOLDERS'], exist_ok=True)
os.makedirs('data', exist_ok=True)

# Initialize RAG components
model = OllamaLLM(model="llama3.1", temperature=0)
text_splitter = CharacterTextSplitter(separator="/n", chunk_size=1000, chunk_overlap=200)
embeddings = HuggingFaceEmbeddings()

def load_knowledge_base(pdf_path):
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    text_chunks = text_splitter.split_documents(documents)
    knowledge_base = FAISS.from_documents(text_chunks, embeddings)
    return RetrievalQA.from_chain_type(model, retriever=knowledge_base.as_retriever())

@app.route('/')
def index():
    folders = os.listdir(app.config['FOLDERS'])
    pdf_files = {}
    subfolders = {}
    pdf_percentages = {}

    for folder in folders:
        folder_path = os.path.join(app.config['FOLDERS'], folder)
        if os.path.isdir(folder_path):
            subfolders[folder] = [d for d in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, d))]
            pdf_files[folder] = {subfolder: [f for f in os.listdir(os.path.join(folder_path, subfolder)) if f.endswith('.pdf')] for subfolder in subfolders[folder]}
            pdf_files[folder][''] = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and f.endswith('.pdf')]

            # Read scroll percentage from the data directory
            for subfolder in pdf_files[folder].keys():
                for pdf in pdf_files[folder][subfolder]:
                    pdf_info_path = os.path.join('data', f'{folder}_{subfolder}_{pdf}.txt')
                    if os.path.exists(pdf_info_path):
                        with open(pdf_info_path, 'r') as file:
                            pdf_percentages[f'{folder}/{subfolder}/{pdf}'] = file.read().strip()
                    else:
                        pdf_percentages[f'{folder}/{subfolder}/{pdf}'] = '0'

    if 'your_notes' not in folders:
        os.makedirs(os.path.join(app.config['FOLDERS'], 'your_notes'), exist_ok=True)

    return render_template('index.html', folders=folders, pdf_files=pdf_files, subfolders=subfolders, pdf_percentages=pdf_percentages)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdf_file' not in request.files:
        return redirect(request.url)
    file = request.files['pdf_file']
    folder = request.form.get('folder', '')
    subfolder = request.form.get('subfolder', '')

    if file and file.filename.endswith('.pdf'):
        filename = file.filename
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)
        if folder:
            if subfolder:
                folder_path = os.path.join(app.config['FOLDERS'], folder, subfolder)
            else:
                folder_path = os.path.join(app.config['FOLDERS'], folder)
            os.makedirs(folder_path, exist_ok=True)
            shutil.move(upload_path, os.path.join(folder_path, filename))
        else:
            # If no folder is selected, save in a default location
            default_folder = 'Default'
            folder_path = os.path.join(app.config['FOLDERS'], default_folder)
            os.makedirs(folder_path, exist_ok=True)
            shutil.move(upload_path, os.path.join(folder_path, filename))
    return redirect(url_for('index'))

@app.route('/move_pdf/<filename>/<source_folder>/<source_subfolder>', methods=['POST'])
def move_pdf(filename, source_folder, source_subfolder=None):
    target_folder = request.form.get('target_folder', source_folder)
    target_subfolder = request.form.get('target_subfolder', '')

    source_path = os.path.join(app.config['FOLDERS'], source_folder, source_subfolder if source_subfolder else '', filename)
    target_path = os.path.join(app.config['FOLDERS'], target_folder, target_subfolder if target_subfolder else '', filename)

    if not os.path.exists(source_path):
        return f"Source file not found: {source_path}", 404

    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.move(source_path, target_path)
    except Exception as e:
        return f"Error moving file: {e}", 500

    return redirect(url_for('index'))

@app.route('/view_pdf/<folder>/<subfolder>/<filename>')
@app.route('/view_pdf/<folder>/<filename>')
def view_pdf(folder, subfolder=None, filename=None):
    # Fetch all folders and subfolders
    folders = os.listdir(app.config['FOLDERS'])
    pdf_files = {}
    subfolders = {}

    if folder in folders:
        folder_path = os.path.join(app.config['FOLDERS'], folder)
        if os.path.isdir(folder_path):
            # List all subfolders
            subfolders[folder] = [d for d in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, d))]
            pdf_files[folder] = {}
            
            for subfolder_name in subfolders[folder]:
                subfolder_path = os.path.join(folder_path, subfolder_name)
                pdf_files[folder][subfolder_name] = [f for f in os.listdir(subfolder_path) if os.path.isfile(os.path.join(subfolder_path, f)) and f.endswith('.pdf')]
            
            # Include PDFs in the main folder if no subfolder
            pdf_files[folder][''] = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and f.endswith('.pdf')]

    return render_template('view_pdf.html', folder=folder, subfolder=subfolder, filename=filename, pdf_files=pdf_files, all_subfolders=subfolders)

@app.route('/serve_pdf/<folder>/<subfolder>/<filename>')
@app.route('/serve_pdf/<folder>/<filename>')
def serve_pdf(folder, subfolder=None, filename=None):
    if subfolder:
        file_path = os.path.join(app.config['FOLDERS'], folder, subfolder, filename)
    else:
        file_path = os.path.join(app.config['FOLDERS'], folder, filename)
    
    print(f"Serving PDF from: {file_path}")  # Debugging statement
    
    if os.path.exists(file_path):
        return send_from_directory(os.path.dirname(file_path), filename)
    else:
        return "PDF file not found.", 404

@app.route('/create_folder', methods=['POST'])
def create_folder():
    new_folder = request.form.get('new_folder')
    if new_folder:
        folder_path = os.path.join(app.config['FOLDERS'], new_folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
    return redirect(url_for('index'))

@app.route('/create_subfolder', methods=['POST'])
def create_subfolder():
    folder = request.form.get('folder')
    new_subfolder = request.form.get('new_subfolder')
    if folder and new_subfolder:
        subfolder_path = os.path.join(app.config['FOLDERS'], folder, new_subfolder)
        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)
    return redirect(url_for('index'))


@app.route('/update_pdf_scroll', methods=['POST'])
def update_pdf_scroll():
    filename = request.form.get('filename')
    folder = request.form.get('folder', '')
    subfolder = request.form.get('subfolder', '')
    scroll_percentage = request.form.get('scroll_percentage', '0')

    # New path for storing the scroll percentage
    pdf_info_path = os.path.join('data', f'{folder}_{subfolder}_{filename}.txt')

    with open(pdf_info_path, 'w') as file:
        file.write(scroll_percentage)

    return '', 204

@app.route('/get_query_history/<folder>/<subfolder>/<filename>')
@app.route('/get_query_history/<folder>/<filename>')
def get_query_history(folder, subfolder=None, filename=None):
    pdf_id = f"{folder}_{subfolder}_{filename}" if subfolder else f"{folder}_{filename}"
    Query_db = Query()
    queries = db.search(Query_db.pdf_id == pdf_id)
    # Add doc_id to each query
    for query in queries:
        query['doc_id'] = query.doc_id
    return jsonify(queries)

@app.route('/delete_query', methods=['POST'])
def delete_query():
    data = request.json
    query_id = data.get('query_id')
    if query_id:
        db.remove(doc_ids=[query_id])
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

@app.route('/query_rag', methods=['POST'])
def query_rag():
    data = request.json
    query = data.get('query')
    filename = data.get('filename')
    folder = data.get('folder')
    subfolder = data.get('subfolder', '')  # Ensure subfolder defaults to an empty string

    # Debugging print statements
    print(f"Query: {query}")
    print(f"Filename: {filename}")
    print(f"Folder: {folder}")
    print(f"Subfolder: '{subfolder}'")

    # Construct the PDF path
    if subfolder:
        pdf_path = os.path.join(app.config['FOLDERS'], folder, subfolder, filename)
    else:
        pdf_path = os.path.join(app.config['FOLDERS'], folder, filename)

    print(f"Constructed PDF path: {pdf_path}")

    if not os.path.exists(pdf_path):
        return jsonify({'response': 'PDF file not found.'}), 404

    # Load the knowledge base for the PDF
    qa_chain = load_knowledge_base(pdf_path)

    # Perform RAG query
    response = qa_chain.invoke(input=query)

    pdf_id = f"{folder}_{subfolder}_{filename}" if subfolder else f"{folder}_{filename}"
    db.insert({
        'pdf_id': pdf_id,
        'query': query,
        'response': response['result'],
        'timestamp': datetime.now().isoformat()
    })

    return jsonify({'response': response['result']})


@app.route('/create_note', methods=['POST'])
def create_note():
    title = request.form.get('title')
    content = request.form.get('note_content')
    
    # Create PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(200, 10, txt=title, ln=1, align='C')
    
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=content)
    
    # Create notes folder if it doesn't exist
    notes_folder = os.path.join(app.config['FOLDERS'], 'your_notes')
    os.makedirs(notes_folder, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{title}_{timestamp}.pdf"
    pdf_path = os.path.join(notes_folder, filename)
    pdf.output(pdf_path)
    
    return redirect(url_for('index'))

@app.route('/delete_pdf/<folder>/<filename>')
@app.route('/delete_pdf/<folder>/<subfolder>/<filename>')
def delete_pdf(folder, subfolder=None, filename=None):
    if subfolder:
        file_path = os.path.join(app.config['FOLDERS'], folder, subfolder, filename)
    else:
        file_path = os.path.join(app.config['FOLDERS'], folder, filename)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        
        # Remove scroll percentage data if exists
        pdf_info_path = os.path.join('data', f'{folder}_{subfolder}_{filename}.txt')
        if os.path.exists(pdf_info_path):
            os.remove(pdf_info_path)
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
