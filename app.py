import os, requests, ast, re
from passcheck import isStrongPassword
from bookinfodb import tellgenre
from flask import Flask, session, request, render_template, g, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

engine = create_engine('postgresql://postgres:keval@localhost/book')
db = scoped_session(sessionmaker(bind=engine))

ENV = 'dev'

if ENV == 'dev':
    app.debug = True
    app.config['SQLALCHEMY_DATABASE_URI']= 'postgresql://postgres:keval@localhost/book'
else:
    app.debug =False

@app.route("/", methods=['GET', 'POST'])
def index():
    return render_template("index.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        
        if db.execute('SELECT userid, pass FROM users WHERE userid = :username and pass = :password', {"username": username, "password":password}).rowcount == 1:
            session["user"] = username
            return redirect(url_for('search'))
        else:
            return render_template("error.html", msg="Username or password invalid", url="index")

    # Already logged in
    elif 'user' in session:
        return render_template("search.html", msgx="Already logged in continue search", username=g.user  )
        # return redirect(url_for('search'))

    else:
        return render_template("login.html")


@app.route('/signup',methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        confirmpassword = request.form.get("repassword")

        # One of the fields empty.
        if (username is "") or (password is "") or (confirmpassword is ""):
            return render_template("error.html", msg="One of the fields is empty.", url="signup")

        # Username must be at least 4 characters long.
        if len(username) < 4:
            return render_template("error.html", msg="Username must be at least 4 characters long.", url="signup")

        # Username cannot contain special characters
        if not username.isalnum():
            return render_template("error.html", msg="Username cannot contain special characters.", url="signup")

        # Checking if username already exists
        if db.execute('SELECT "userid" FROM "users" WHERE "userid" = :username',
            {"username": username}).rowcount > 0:
            return render_template("error.html", msg="The username already exists.", url="signup")

        # Check if it is a strong password
        if not isStrongPassword(password):
            return render_template("error.html", msg="Your password must be at least 6 characters and at most 20 characters, and contain\
             at least one lowercase letter, at least one uppercase letter, and at least one digit.", url="signup")

        # Check if the password match
        if not password == confirmpassword:
            return render_template("error.html", msg="Your password does not match.", url="signup")

        # Insert into database
        db.execute('INSERT INTO "users" ("userid", "pass") VALUES (:username, :password)',
            {"username":username, "password":password})
        db.commit()

        session["user"] = username

        return redirect(url_for('search'))

    else:
        return render_template("signup.html")




@app.route('/search',methods=['GET', 'POST'])
def search():
    # Display Search Bar
    if g.user and request.method == 'GET':
        return render_template("search.html", username=g.user )

    elif g.user and request.method == 'POST':
        search = request.form.get("search")

        if len(search) == 0 or (not search.isalnum()):
            return render_template("error.html", msg="Invalid search.", url="search")

        return redirect(url_for('listob', search=search, username=g.user))

    else:
        return render_template("error.html", msg="Please login first.", url="index")

@app.route("/search/<string:search>")
def listob(search):
    if g.user:
        result = db.execute('SELECT "title", "author", "year", "isbn" FROM "bookinfo" WHERE UPPER("title") LIKE UPPER(:search)\
            OR UPPER("author") LIKE UPPER(:search) OR UPPER("isbn") LIKE UPPER(:search)', {"search":'%'+search+'%'}).fetchall()

        return render_template("listob.html", result=result, username=g.user)

    else:
        return render_template("error.html", msg="Please login first.", url="index")





@app.route("/info", methods=['GET', 'POST'])
def info():
    if g.user and (request.method == "GET" or request.method == "POST"):
        title, author, year, isbn = request.args.get("title"), request.args.get("author"), request.args.get("year"), request.args.get("isbn")

        if request.method == "POST":
            rating = request.form.get("rating")
            review = request.form.get("review")
            username = str(g.user)

            # No ratings selected
            if rating == "Ratings":
                return render_template("error.html", msg="Please rate the book.", url="search")

            # Already submitted a review
            if isBookInBookreview(isbn):
                usernameList = str(db.execute('SELECT "usernames" FROM "bookreview" WHERE "isbn" = :isbn', {"isbn": isbn}).fetchone())
                usernameList = usernameList[2:len(usernameList) - 3]
                usernameList = ast.literal_eval(usernameList)

                if username in usernameList:
                    return render_template("error.html", msg="You already reviewed this book.", url="search")

            # No optional review
            if not review:
                # If the book exists in the table
                if isBookInBookreview(isbn):
                    usernames = str(db.execute('SELECT "usernames" FROM "bookreview" WHERE "isbn" = :isbn', {"isbn": isbn}).fetchone())
                    usernames = usernames[2:len(usernames) - 3]
                    usernames = ast.literal_eval(usernames)
                    usernames.append(username)
                    usernames = str(usernames)

                    db.execute('UPDATE "bookreview" SET "ratings" = "ratings" + :ratings, "ratingsNum" = "ratingsNum" + 1, "usernames" = :usernames WHERE \
                    "isbn"=:isbn', {"ratings":rating, "usernames":usernames, "isbn":isbn})
                    db.commit()

                # Book does not exist
                else:
                    usernameString = str([usernameList])
                    # Insert into database
                    db.execute('INSERT INTO "bookreview" ("isbn", "ratings", "ratingsNum", "usernames") VALUES (:isbn, :ratings, :ratingsNum, :username)',
                        {"isbn":isbn, "ratings":rating, "ratingsNum": 1, "username":usernameString})
                    db.commit()

            # Optional review
            else:
                # If the book exists in the table
                if isBookInBookreview(isbn):
                    usernames = str(db.execute('SELECT "usernames" FROM "bookreview" WHERE "isbn" = :isbn', {"isbn": isbn}).fetchone())
                    usernames = usernames[2:len(usernames) - 3]
                    usernames = ast.literal_eval(usernames)
                    usernames.append(username)
                    usernames = str(usernames)

                    reviews = str(db.execute('SELECT "reviews" FROM "bookreview" WHERE "isbn" = :isbn', {"isbn": isbn}).fetchone())
                    reviews = reviews.replace("\\", "")
                    temp = reviews[1:len(reviews) - 2]

                    # The book exists but no reviews yet
                    if temp == "None":
                        reviews = str({username:review})

                    # The book has a review already
                    else:
                        reviews = reviews[2:len(reviews) - 3]
                        reviews = ast.literal_eval(reviews)
                        reviews[username] = review
                        reviews = str(reviews)

                    db.execute('UPDATE "bookreview" SET "ratings" = "ratings" + :ratings, "ratingsNum" = "ratingsNum" + 1, "usernames" = :usernames, "reviews" = :reviews WHERE \
                    "isbn" = :isbn', {"ratings":rating, "usernames":usernames, "reviews":reviews, "isbn":isbn})
                    db.commit()

                # Book does not exist
                else:
                    usernameList = [username]
                    usernameString = str(usernameList)
                    reviews = str({username:review})

                    # Insert into database
                    db.execute('INSERT INTO "bookreview" ("isbn", "ratings", "ratingsNum", "usernames", "reviews") VALUES (:isbn, :ratings, :ratingsNum, :username, :reviews)',
                        {"isbn":isbn, "ratings":rating, "ratingsNum": 1, "username":usernameString, "reviews":reviews})
                    db.commit()

        rating, ratingNum, avgRating = 0, 0, 0.0
        reviews = ""

        # Check if the book exists in the table
        if isBookInBookreview(isbn):
            rating = list(db.execute('SELECT "ratings" FROM "bookreview" WHERE "isbn" = :isbn', {"isbn": isbn}).fetchone())[0]
            ratingNum = list(db.execute('SELECT "ratingsNum" FROM "bookreview" WHERE "isbn" = :isbn', {"isbn": isbn}).fetchone())[0]
            avgRating = round( int(rating) / int(ratingNum), 2)

            reviews = str(db.execute('SELECT "reviews" FROM "bookreview" WHERE "isbn" = :isbn', {"isbn": isbn}).fetchone())
            reviews = reviews.replace("\\", "")
            temp = reviews[1:len(reviews) - 2]

            if temp != "None":
                reviews = reviews[2:len(reviews) - 3]
                reviews = ast.literal_eval(reviews)
            else:
                reviews = None

        return render_template("info.html", title=title, author=author, year=year, isbn=isbn,
            avgRating=avgRating, ratingNum=ratingNum, reviews=reviews)

    else:
        return render_template("error.html", msg="Please login first.", url="index")


def isBookInBookreview(isbn):
    return db.execute('SELECT "isbn" FROM "bookreview" WHERE "isbn" = :isbn', {"isbn": isbn}).rowcount > 0

@app.route('/suggestion',methods=['GET', 'POST'])
def suggestion():
    # Display Search Bar
    if g.user and request.method == 'GET':
        return render_template("suggestion.html", username=g.user )

    elif g.user and request.method == 'POST':
        suggestionstr = request.form.get("suggestion")

        if len(suggestionstr) == 0:
            return render_template("error.html", msg="Invalid search.", url="suggestion")

        else :
            outlist = tellgenre(suggestionstr)
            return render_template("suggestion.html", olist= outlist , username=g.user)


    else:
        return render_template("error.html", msg="Please login first.", url="index")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for('login'))


@app.before_request
def before_request():
    g.user = None
    if 'user' in session:
        g.user = session['user']


if __name__ == "__main__":
    app.run()
