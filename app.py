from flask import Flask, render_template, request, redirect, jsonify, send_file
from groq import Groq
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)
from reportlab.pdfgen import canvas
from docx import Document
from gtts import gTTS

import sqlite3
import os
import uuid


# =====================
# CONFIG
# =====================

load_dotenv()



app = Flask(__name__)
app.secret_key = SECRET_KEY

login_manager = LoginManager()
login_manager.init_app(app)

SECRET_KEY = st.secrets.get("SECRET_KEY", "secret")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

#login_manager.login_view = "login"

DB = "database.db"

os.makedirs("exports", exist_ok=True)


# =====================
# DATABASE
# =====================

def db():
    return sqlite3.connect(DB)


def init_db():
    con = db()
    
    con.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    
    con.execute("""
        CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            topic TEXT,
            action TEXT,
            content TEXT
        )
    """)
    
    con.commit()
    con.close()


init_db()


# =====================
# USER
# =====================

class User(UserMixin):
    def __init__(self, data):
        self.id = data[0]
        self.username = data[1]


#


# =====================
# GEMINI
# =====================

def generate(prompt):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print("AI Error:", e)

        return "AI Error: " + str(e)
        
        # Fallback content
        if "quiz" in prompt.lower():
            return """
1. What is Python?
A) Language
B) Animal
C) Tool
D) Game

Answer: A
"""
        
        if "flashcard" in prompt.lower():
            return """
Question: What is Python?
Answer: A programming language.
"""
        
        if "mind map" in prompt.lower():
            return """
Topic
 |
 |-- Main Concept
 |     |-- Point 1
 |     |-- Point 2
"""
        
        if "notes" in prompt.lower():
            return """
Notes:

• Main idea
• Important points
• Examples
"""
        
        return "AI Error: " + str(e)


def save_history(topic, action, content):
    con = db()
    con.execute(
        """
        INSERT INTO history (username, topic, action, content)
        VALUES (?, ?, ?, ?)
        """,
        (current_user.username, topic, action, content)
    )
    con.commit()
    con.close()


# =====================
# AUTH
# =====================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if not username or not password:
            return "Username and password required"
        
        con = db()
        
        try:
            con.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            con.commit()
        except Exception:
            con.close()
            return "Username already exists"
        
        con.close()
        return redirect("/login")
    
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if not username or not password:
            return "Username and password required"
        
        con = db()
        user = con.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        con.close()
        
        if user and check_password_hash(user[2], password):
            login_user(User(user))
            return redirect("/")
        
        return "Invalid login"
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect("/login")


# =====================
# HOME
# =====================

@app.route("/")
@login_required
def home():
    return render_template("index.html")


# =====================
# AI FEATURES
# =====================

@app.route("/generate", methods=["POST"])
@login_required
def generate_ai():
    topic = request.form.get("topic", "").strip()
    action = request.form.get("action", "").strip()
    
    prompts = {
        "explain": f"""
Explain the topic in very simple English.

Topic: {topic}

Format:

# Topic Name

## Meaning
- Bullet points

## Importance
- Bullet points

## Examples
- Bullet points

## Advantages
- Bullet points

## Quick Revision
- 5 short bullet points

Keep sentences short and easy for students.
""",
        "notes": f"""
Create student-friendly study notes.

Topic: {topic}

Rules:
- Use simple English
- Use headings
- Use bullet points
- Keep explanations short
- Give examples
- Highlight important concepts

Format:

# Topic

## Introduction
- Point

## Main Concepts
- Point
- Point

## Examples
- Example

## Important Points
- Point

## Revision Notes
- Point
""",
        "summary": f"""
Create an easy summary.

Topic: {topic}

Rules:
- Very simple English
- Short sentences
- Bullet points only

Format:

# Summary

- Point 1
- Point 2
- Point 3
- Point 4
- Point 5

## Key Takeaways
- Point
- Point
""",
        "quiz": f"""
Create 20 multiple choice questions.

Topic: {topic}

Use simple English.

Format:

### Question 1

Question text

A)
B)
C)
D)

Answer:

Explanation:
""",

    "flashcards": f"""
Create 20 flashcards for students.

Topic:
{topic}

Rules:
- Use simple English
- Keep answers short
- Use clear format

Format:

# Flashcards

## Card 1

Question:
- Write question here

Answer:
- Write answer here


## Card 2

Question:
- Write question here

Answer:
- Write answer here
""",
        "fill": f"""
Create 20 fill in the blanks questions.

Topic:
{topic}
""",
        "mindmap": f"""
Create a simple mind map.

Topic:
{topic}

Rules:
- Use simple English
- Use short points
- Show main idea and branches

Format:

# Mind Map

Topic
|
|-- Main Idea
|     |
|     |-- Point 1
|     |-- Point 2
|
|-- Examples
|     |
|     |-- Example 1
|     |-- Example 2
|
|-- Important Notes
      |
      |-- Note 1
      |-- Note 2
""",
        "cheat": f"""
Create a cheat sheet.

Topic:
{topic}
""",
        "interview": f"""
Create interview questions and answers for students.

Topic:
{topic}

Rules:
- Use simple English
- Keep answers short
- Use clear headings
- Add important points
- Avoid difficult words

Format:

# Interview Questions

## Question 1

Question:
- Write question here

Answer:
- Write simple answer here

Key Points:
- Point 1
- Point 2


## Question 2

Question:
- Write question here

Answer:
- Write simple answer here

Key Points:
- Point 1
- Point 2
"""
    }
    
    if action not in prompts:
        return jsonify({"error": "Invalid action"})
    
    result = generate(prompts[action])
    save_history(topic, action, result)
    
    return jsonify({"content": result})


# =====================
# EXPORTS
# =====================

@app.route("/pdf")
@login_required
def pdf():
    text = request.args.get("text", "")
    file = f"exports/{uuid.uuid4()}.pdf"
    
    c = canvas.Canvas(file)
    y = 800
    
    for line in text.split("\n"):
        c.drawString(40, y, line[:100])
        y -= 15
        if y < 50:
            c.showPage()
            y = 800
    
    c.save()
    return send_file(file)


@app.route("/docx")
@login_required
def docx_file():
    text = request.args.get("text", "")
    file = f"exports/{uuid.uuid4()}.docx"
    
    doc = Document()
    doc.add_paragraph(text)
    doc.save(file)
    
    return send_file(file)


@app.route("/audio")
@login_required
def audio():
    text = request.args.get("text", "")
    file = f"exports/{uuid.uuid4()}.mp3"
    
    gTTS(text).save(file)
    
    return send_file(file)


# =====================
# START
# =====================

if __name__ == "__main__":
    app.run(debug=True)
