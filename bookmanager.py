# bookmanager.py
from flask import Flask, render_template, request, redirect, jsonify
import os
import json
import csv
import xml.etree.ElementTree as ET
import pandas as pd
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xml', 'xlsx', 'json'}
BOOKS_FILE = 'books.json'

# Initialize books storage
def load_books():
    if os.path.exists(BOOKS_FILE):
        with open(BOOKS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_books(books):
    with open(BOOKS_FILE, 'w') as f:
        json.dump(books, f, indent=2)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=['GET', 'POST'])
def home():
    books = load_books()
    if request.method == 'POST':
        new_book = {
            'title': request.form.get('title'),
            'author': request.form.get('author', ''),
            'isbn': request.form.get('isbn', '')
        }
        books.append(new_book)
        save_books(books)
    return render_template('home.html', books=books)

@app.route("/api/books", methods=['POST'])
def add_book_json():
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    data = request.get_json()
    
    # Validate JSON data
    if 'title' not in data:
        return jsonify({"error": "Title is required"}), 400
    
    books = load_books()
    books.append({
        'title': data['title'],
        'author': data.get('author', ''),
        'isbn': data.get('isbn', '')
    })
    save_books(books)
    return jsonify(data), 201

@app.route("/upload", methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            # Process different file formats
            if filename.endswith('.csv'):
                process_csv(file_path)
            elif filename.endswith('.xml'):
                process_xml(file_path)
            elif filename.endswith('.xlsx'):
                process_excel(file_path)
            elif filename.endswith('.json'):
                process_json(file_path)
            
            os.remove(file_path)  # Clean up uploaded file
            return jsonify({"message": "File processed successfully"}), 200
        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({"error": str(e)}), 400
    
    return jsonify({"error": "File type not allowed"}), 400

def process_csv(file_path):
    books = load_books()
    with open(file_path, 'r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if 'title' in row:
                books.append({
                    'title': row['title'],
                    'author': row.get('author', ''),
                    'isbn': row.get('isbn', '')
                })
    save_books(books)

def process_xml(file_path):
    books = load_books()
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    for book_elem in root.findall('book'):
        title_elem = book_elem.find('title')
        if title_elem is not None:
            books.append({
                'title': title_elem.text,
                'author': book_elem.find('author').text if book_elem.find('author') is not None else '',
                'isbn': book_elem.find('isbn').text if book_elem.find('isbn') is not None else ''
            })
    save_books(books)

def process_excel(file_path):
    books = load_books()
    df = pd.read_excel(file_path)
    for _, row in df.iterrows():
        if 'title' in row:
            books.append({
                'title': row['title'],
                'author': row.get('author', ''),
                'isbn': row.get('isbn', '')
            })
    save_books(books)

def process_json(file_path):
    books = load_books()
    with open(file_path, 'r') as file:
        data = json.load(file)
        for book_data in data:
            if 'title' in book_data:
                books.append({
                    'title': book_data['title'],
                    'author': book_data.get('author', ''),
                    'isbn': book_data.get('isbn', '')
                })
    save_books(books)

@app.route("/update", methods=['POST'])
def update():
    books = load_books()
    oldtitle = request.form.get('oldtitle')
    newtitle = request.form.get('newtitle')

    for book in books:
        if book['title'] == oldtitle:
            book['title'] = newtitle
            break
    
    save_books(books)
    return redirect("/")

@app.route("/delete", methods=["POST"])
def delete():
    books = load_books()
    title = request.form.get("title")
    
    books = [book for book in books if book['title'] != title]
    save_books(books)
    return redirect("/")

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    if not os.path.exists(BOOKS_FILE):
        save_books([])
    app.run(debug=True, port=8080)
