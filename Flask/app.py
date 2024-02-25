from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf
from markupsafe import Markup
import utils


# from sklearn import utils
from werkzeug.security import generate_password_hash, check_password_hash
from utils import disease_dic

from model import predict_image

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a real secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
csrf = CSRFProtect(app)  # Initialize CSRF protection

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# Define a function to create database tables
def create_tables():
    with app.app_context():
        db.create_all()

# Call the function to create database tables
create_tables()

@app.route('/login', methods=['GET', 'POST'])
def login():
    csrf_token = generate_csrf()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['loggedin'] = True
            session['username'] = username  # Store username in session
            return redirect(url_for('home'))
        else:
            return "Failed login", 401
    return render_template('login.html', csrf_token=csrf_token)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')  # Corrected method
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout', methods=['POST'])  # Adjusted to handle POST method
def logout():
    if request.method == 'POST':
        session.pop('loggedin', None)
        session.pop('username', None)  # Remove username from session
        return redirect(url_for('login'))
    # Redirect to login if logout route is accessed via GET method
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
def home():
    if not session.get('loggedin'):
        # Redirect to login if not logged in
        return redirect(url_for('login'))
    
    # Generate CSRF token
    csrf_token = generate_csrf()
    
    return render_template('index.html', csrf_token=csrf_token, username=session.get('username'))

# @app.route('/predict', methods=['GET', 'POST'])
# def predict():
#     csrf_token = generate_csrf()  # Generate CSRF token
#     if request.method == 'POST':
#         try:
#             file = request.files['file']
#             img = file.read()
#             prediction = predict_image(img)
#             print(prediction)
#             res = Markup(utils.disease_dic[prediction])
#             return render_template('display.html', status=200, result=res,csrf_token=csrf_token)
#         except:
#             pass
#     return render_template('index.html', status=500, res="Internal Server Error",csrf_token=csrf_token)
@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        try:
            file = request.files['file']
            img = file.read()
            prediction = predict_image(img)
            print(prediction)
            res = Markup(utils.disease_dic[prediction])
            return render_template('display.html', status=200, result=res)
        except:
            pass
    return render_template('index.html', status=500, res="Internal Server Error")
if __name__ == "__main__":
    app.run(debug=True)
