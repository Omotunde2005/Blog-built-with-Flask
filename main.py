import time
import os
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, URLField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditor, CKEditorField
from datetime import date
from forms import RegistrationForm, LoginForm, CommentForm, ContactForm, MailForm
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, foreign
from sqlalchemy.ext.declarative import declarative_base
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from functools import wraps
from flask_gravatar import Gravatar
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime as dt
load_dotenv()
YEAR = dt.datetime.now().year


app = Flask(__name__)

ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app, size=60, rating='g', default='retro',
                    force_default=False, force_lower=False, use_ssl=False, base_url=None)
# CONNECT TO DB

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'my_app_secret_key'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
app.secret_key = 'Edun2005retweetme'


# CONFIGURE TABLE
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    comments = relationship("Comment", back_populates="comment_author")
    posts = relationship("BlogPost", back_populates="author")


class BlogPost(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_text = db.Column(db.String, nullable=False)
    comment_author = relationship("User", back_populates="comments")
    parent_post = relationship("BlogPost", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"))

#db.create_all()


def admin_only(f):
    @wraps(f)
    def wrapper_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)

    return wrapper_function


# WTForm
class CreatePostForm(FlaskForm):
    title = StringField("Blog Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    author = StringField("Your Name", validators=[DataRequired()])
    img_url = URLField("Blog Image URL", validators=[DataRequired(), URL()])
    body = CKEditorField("Blog Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/', methods=["GET"])
def get_all_posts():
    posts = db.session.query(BlogPost).all()
    
    return render_template("new_index.html", all_posts=posts, user=current_user, year=YEAR)
    


@app.route("/post/<int:index>", methods=["POST", "GET"])
def show_post(index):
    required = BlogPost.query.filter_by(id=index).first()
    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for('login'))
        new_comment = Comment(
            comment_text=form.comments.data,
            comment_author=current_user,
            parent_post=required,
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('get_all_posts'))
    
    requested_post = None
    posts = db.session.query(BlogPost).all()
    for blog_post in posts:
        if blog_post.id == index:
            requested_post = blog_post
            return render_template("new_post.html", post=requested_post, user=current_user, form=form, year=YEAR)


@app.route("/about")
def about():
    return render_template("about.html", user=current_user, year=YEAR)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login to send the message. You don't have an account? Kindly Register.")
            return redirect(url_for('login'))                    
                 
    return render_template("contact.html", user=current_user, form=form, year=YEAR)


@app.route("/make-post", methods=["GET", "POST"])
@admin_only
def make_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            date=date.today().strftime("%B %d, %Y"),
            img_url=form.img_url.data,
            author=current_user
            )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('get_all_posts'))
    word = "New post"
    return render_template('make-post.html', form=form, word=word, user=current_user, year=YEAR)


@app.route("/edit_post/<int:id>")
@admin_only
def edit(id):
    blog_post = BlogPost.query.filter_by(id=id).first()
    form = CreatePostForm(
        title=blog_post.title,
        subtitle=blog_post.subtitle,
        body=blog_post.body,
        author=blog_post.author,
        img_url=blog_post.img_url,
    )
    word = "Edit Post"
    db.session.delete(blog_post)
    db.session.commit()
    return render_template('make-post.html', form=form, word=word, year=YEAR, user=current_user)


@app.route("/delete/<int:id>")
@admin_only
def delete(id):
    blog_post = BlogPost.query.filter_by(id=id).first()
    db.session.delete(blog_post)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/login", methods=["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        correct_pass = check_password_hash(pwhash=user.password, password=form.password.data)
        if user:
            if correct_pass:
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash("The password you entered does not match your email")
                return redirect(url_for('login'))
        else:
            flash("The email you entered is not registered")
            return redirect(url_for('login'))
    return render_template("login.html", form=form, user=current_user, year=YEAR)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        check = User.query.filter_by(email=form.email.data).first()
        if check:
            flash("The email you entered is registered. Log in instead")
            return redirect(url_for('login'))
        hashed_password = generate_password_hash(password=form.password.data, method="pbkdf2:sha256", salt_length=int(8))
        new_user = User(
            name=form.name.data,
            email=form.email.data,
            password=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Registration Successful")
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form, user=current_user, year=YEAR)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))




if __name__ == "__main__":
    app.run(debug=True)
