import os
import requests

from flask import Flask, session, flash, jsonify, redirect, render_template, request
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
import json


app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))



def login_required(f):
    """    Decorate routes to require login.    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code

def lookup(isbn):
    """Look up goodreads for ratings of a book."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        response = requests.get(f"https://www.goodreads.com/book/review_counts.json?isbns={isbn}&key={api_key}")
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        gr = response.json()
        gr_book=gr["books"][0]       
        return {
            "count": int(gr_book["ratings_count"]),
            "average": float(gr_book["average_rating"])
        }
    except (KeyError, TypeError, ValueError):
        return None




@app.route("/", methods=["GET"])
@login_required
def index():
    rows = db.execute("SELECT * FROM users WHERE id = :id", {"id": session["user_id"]}).fetchall()
    return render_template("search.html", username=rows[0]["username"])


@app.route("/register", methods=["GET", "POST"])
def register():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        """Register user"""

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation", 400)

        # Ensure confirmation is identical to password
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("confirmation and passowrd mismatch", 400)

        if db.execute("SELECT * FROM users WHERE username = :username", {"username": request.form.get("username")}).rowcount == 0:
            db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", {"username": request.form.get("username"), "hash": generate_password_hash(request.form.get("password"))})
            
            # Query database for username
            rows = db.execute("SELECT * FROM users WHERE username = :username", {"username": request.form.get("username")}).fetchall()
            # Remember which user has logged in
            session["user_id"] = rows[0]["id"]
            db.commit()

            # Redirect user to home page
            return redirect("/", 200)
        else:
            return apology("Username already exists", 400)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
   

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          {"username": request.form.get("username")}).fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/search")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        """Search for the desired book."""

        rows = db.execute("SELECT * FROM users WHERE id = :id", {"id": session["user_id"]}).fetchall()

        # Ensure there was an input
        if not request.form.get("book-search"):
            return apology("Must provide ISBN, Title or Author of the book", 400)

        val = "%"+request.form.get("book-search").lower()+"%"

        
        books = db.execute("SELECT * FROM books WHERE LOWER(isbn) LIKE :val OR LOWER(book_name) LIKE :val OR LOWER(author) LIKE :val", {"val": val}).fetchall()
     
        if not books:
            return apology("Found Nothing", 404)
        else:
            return render_template("books.html", books=books, username=rows[0]["username"])           

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        rows = db.execute("SELECT * FROM users WHERE id = :id", {"id": session["user_id"]}).fetchall()
        return render_template("search.html", username=rows[0]["username"])


@app.route("/books/<isbn>", methods=["GET", "POST"])
def book(isbn):
    
    # User reached route via POST (as by clicking a link or via redirect)
    if request.method == "GET":

        """Lists details about a single book."""

        # Make sure book exists.
        book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
        if not book:
            return render_template(apology("Found Nothing", 404))
        # Get all rewviews.
        reviews = db.execute("SELECT * FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()
    
        show_form = 1
        tab = []
        for review in reviews:
            username=db.execute("SELECT username FROM users WHERE id = :id", {"id": review["user_id"]}).fetchone()
            tab.append([username["username"], review["review"], review["rating"]])
            if review["user_id"] == session["user_id"]:
                show_form = 0
        rows = db.execute("SELECT * FROM users WHERE id = :id", {"id": session["user_id"]}).fetchall()
        gr_rating = lookup(isbn)
        return render_template("book.html", book=book, tab=tab, show_form=show_form, username=rows[0]["username"], gr_rating=gr_rating)
    
    # User reached route via POST (submitted a review)
    else:
        """Lists details about a single book."""
        reviews = db.execute("SELECT * FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()
        for review in reviews:
            if review["user_id"] == session["user_id"]:
                return render_template(apology("You can review a book only once!", 403))
        db.execute("INSERT INTO reviews (isbn, user_id, review, rating) VALUES(:isbn, :user_id, :review, :rating)", {"isbn": isbn, "user_id": session["user_id"], "review": request.form.get("book-review"), "rating": request.form.get("book-rating")})
        db.commit()
        book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
        reviews = db.execute("SELECT * FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()
        tab = []
        for review in reviews:
            username=db.execute("SELECT username FROM users WHERE id = :id", {"id": review["user_id"]}).fetchone()
            tab.append([username["username"], review["review"], review["rating"]])
        rows = db.execute("SELECT * FROM users WHERE id = :id", {"id": session["user_id"]}).fetchall()
        gr_rating = lookup(isbn)
        return render_template("book.html", book=book, tab=tab, show_form=0, username=rows[0]["username"], gr_rating=gr_rating)
                

@app.route("/api/<isbn>", methods=["GET"])
def api(isbn):

    # Make sure book exists.    
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if not book:
        return render_template(apology("Found Nothing", 404))
    # Get all rewviews.
    reviews = db.execute("SELECT * FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()
    ratings=0
    for review in reviews:
        ratings=ratings+review["rating"]
    
    book_data = {
        "title": book["book_name"],
        "author": book["author"],
        "year": book["ed_year"],
        "isbn": book["isbn"],
        "review_count": len(reviews),
        "average_score": ratings/len(reviews)
    }
    json_data = json.dumps(book_data, indent=4)
    return(json_data)
    

@app.route("/change_pass", methods=["GET", "POST"])
@login_required
def change_pass():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        """Change Password"""

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide current password", 400)

        # Ensure password is correct
        elif not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid password", 403)

        # Ensure password was submitted
        elif not request.form.get("new_password"):
            return apology("must provide new password", 400)

        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation", 400)

        # Ensure confirmation is identical to password
        elif request.form.get("new_password") != request.form.get("confirmation"):
            return apology("confirmation and passowrd mismatch", 400)

        db.execute(f"UPDATE users SET 'hash'= :hash WHERE id = :id",
                   id=session["user_id"], hash=generate_password_hash(request.form.get("new_password")))
        # Redirect user to home page
        return redirect("/login", 200)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        rows = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        return render_template("change_pass.html", username=rows[0]["username"])