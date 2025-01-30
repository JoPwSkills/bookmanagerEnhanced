from flask import Flask, render_template, request, redirect, jsonify, url_for, flash, session
from functools import wraps
import jwt
import datetime
import os
import json
import csv
import xml.etree.ElementTree as ET
import pandas as pd
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a secure secret key
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'csv', 'xml', 'xlsx', 'json'}
BOOKS_FILE = 'books.json'
USERS_FILE = 'users.json'


# Helper Functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'token' not in session:
            flash('Please login first')
            return redirect(url_for('login'))

        try:
            data = jwt.decode(session['token'], app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data['username']
        except:
            flash('Session expired. Please login again')
            return redirect(url_for('login'))

        return f(current_user, *args, **kwargs)

    return decorated

# File Management Functions
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def load_books():
    if os.path.exists(BOOKS_FILE):
        with open(BOOKS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_books(books):
    with open(BOOKS_FILE, 'w') as f:
        json.dump(books, f, indent=2)

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        users = load_users()
        
        if username in users and check_password_hash(users[username]['password'], password):
            token = jwt.encode({
                'username': username,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }, app.config['SECRET_KEY'])
            
            session['token'] = token
            flash('Login successful!')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not username or not password:
            flash('Username and password are required')
            return render_template('register.html')
        
        users = load_users()
        
        if username in users:
            flash('Username already exists')
        elif password != confirm_password:
            flash('Passwords do not match')
        else:
            users[username] = {
                'password': generate_password_hash(password),
                'role': 'user'
            }
            save_users(users)
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('token', None)
    flash('Logged out successfully')
    return redirect(url_for('login'))

# Book Management Routes
@app.route("/", methods=['GET', 'POST'])
@token_required
def home(current_user):
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author', '')
        isbn = request.form.get('isbn', '')
        
        if not title:
            flash('Title is required!')
            return redirect(url_for('home'))
        
        books = load_books()
        books.append({
            'title': title,
            'author': author,
            'isbn': isbn,
            'added_by': current_user
        })
        save_books(books)
        flash('Book added successfully!')
        
    books = load_books()
    return render_template('home.html', books=books, username=current_user)

@app.route("/upload", methods=['POST'])
@token_required
def upload_file(current_user):
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('home'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('home'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            file.save(filepath)
            process_file(filepath, filename, current_user)
            os.remove(filepath)
            flash('File processed successfully!')
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            flash(f'Error processing file: {str(e)}')
    else:
        flash('Invalid file type')
    return redirect(url_for('home'))

def process_file(filepath, filename, current_user):
    books = load_books()
    new_books = []

    if filename.endswith('.csv'):
        with open(filepath, 'r') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                if 'title' in row:
                    new_books.append({
                        'title': row['title'],
                        'author': row.get('author', ''),
                        'isbn': row.get('isbn', ''),
                        'added_by': current_user
                    })

    elif filename.endswith('.xml'):
        tree = ET.parse(filepath)
        root = tree.getroot()
        for book_elem in root.findall('book'):
            title = book_elem.find('title')
            if title is not None:
                new_books.append({
                    'title': title.text,
                    'author': book_elem.find('author').text if book_elem.find('author') is not None else '',
                    'isbn': book_elem.find('isbn').text if book_elem.find('isbn') is not None else '',
                    'added_by': current_user
                })

    elif filename.endswith('.xlsx'):
        df = pd.read_excel(filepath)
        for _, row in df.iterrows():
            if 'title' in row:
                new_books.append({
                    'title': row['title'],
                    'author': row.get('author', ''),
                    'isbn': row.get('isbn', ''),
                    'added_by': current_user
                })

    elif filename.endswith('.json'):
        with open(filepath, 'r') as file:
            data = json.load(file)
            for book in data:
                if 'title' in book:
                    book['added_by'] = current_user
                    new_books.append(book)

    books.extend(new_books)
    save_books(books)

@app.route("/update", methods=['POST'])
@token_required
def update(current_user):
    oldtitle = request.form.get('oldtitle')
    newtitle = request.form.get('newtitle')
    
    if not newtitle:
        flash('New title is required!')
        return redirect(url_for('home'))
    
    books = load_books()
    updated = False
    
    for book in books:
        if book['title'] == oldtitle and book['added_by'] == current_user:
            book['title'] = newtitle
            updated = True
            break
    
    if updated:
        save_books(books)
        flash('Book updated successfully!')
    else:
        flash('Book not found or you do not have permission to update it')
    
    return redirect(url_for('home'))

@app.route("/delete", methods=['POST'])
@token_required
def delete(current_user):
    title = request.form.get('title')
    if not title:
        flash('Title is required!')
        return redirect(url_for('home'))
    
    books = load_books()
    initial_count = len(books)
    books = [book for book in books if not (book['title'] == title and book['added_by'] == current_user)]
    
    if len(books) < initial_count:
        save_books(books)
        flash('Book deleted successfully!')
    else:
        flash('Book not found or you do not have permission to delete it')
    
    return redirect(url_for('home'))

@app.route('/search')
@token_required
def search(current_user):
    query = request.args.get('query', '').lower()
    books = load_books()
    if query:
        books = [book for book in books if 
                query in book['title'].lower() or 
                query in book['author'].lower() or 
                query in book['isbn'].lower()]
    return render_template('home.html', books=books, username=current_user)

def init_app():
    # Create necessary directories and files
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    if not os.path.exists(BOOKS_FILE):
        save_books([])
    if not os.path.exists(USERS_FILE):
        save_users({})

if __name__ == '__main__':
    init_app()
    app.run(debug=True, port=8080)
