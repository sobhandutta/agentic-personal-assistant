"""
Run this script once to create and populate personal.db with your data.
Edit the values below to reflect your actual profile before running.

Usage:
    python data/seed_db.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "personal.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skills (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL,
    level  TEXT NOT NULL,       -- beginner / intermediate / advanced / expert
    years  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS experience (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company     TEXT NOT NULL,
    role        TEXT NOT NULL,
    start_year  INTEGER,
    end_year    INTEGER,        -- NULL means current
    description TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    tech_stack  TEXT,
    url         TEXT
);

CREATE TABLE IF NOT EXISTS education (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    institution     TEXT NOT NULL,
    degree          TEXT NOT NULL,
    year_graduated  INTEGER
);
"""

PROFILE = [
    ("name",        "Sobhan Dutta"),
    ("email",       "sobhandutta@gmail.com"),
    ("location",    "San Francisco, US"),
    ("headline",    "AI/ML Engineer | LLM Applications | UX Engineering"),
    ("summary",     "Passionate engineer building intelligent systems with large language models. "
                    "Focused on agentic architectures, RAG pipelines, and production ML."),
    ("github",      "https://github.com/sobhandutta"),
    ("website",     "https://sobhandutta.myportfolio.com/about"),
    ("youtube",     "https://www.youtube.com/@baybongdiary"),
    ("languages",   "English (fluent), Bengali (native)"),
    ("availability","Open to new opportunities"),
]

SKILLS = [
    ("Python",          "expert",        6),
    ("Machine Learning","advanced",      4),
    ("LLMs / Prompt Engineering", "advanced", 2),
    ("RAG / Vector DBs","intermediate",  2),
    ("SQL / SQLite",    "advanced",      5),
    ("FastAPI",         "intermediate",  3),
    ("Docker",          "intermediate",  3),
    ("AWS",             "intermediate",  2),
    ("JavaScript",      "intermediate",  3),
    ("React",           "beginner",      1),
]

EXPERIENCE = [
    ("Acme Corp",       "Senior ML Engineer",    2022, None,
     "Led development of an LLM-powered document intelligence platform. "
     "Built RAG pipelines, fine-tuned models, and deployed to AWS."),
    ("TechStart Ltd",   "Data Scientist",        2020, 2022,
     "Built predictive models for customer churn and revenue forecasting. "
     "Delivered dashboards and automated reporting pipelines."),
    ("DataFlow",        "Python Developer",      2018, 2020,
     "Developed ETL pipelines and REST APIs for a SaaS analytics product."),
]

PROJECTS = [
    ("Personal AI Assistant",
     "Multi-agent AI system that answers personal questions by querying SQLite, "
     "Google Drive, Gmail, and LinkedIn.",
     "Python, Anthropic Claude, Gradio, SQLite, Google APIs",
     "https://github.com/sobhandutta/personal-ai-assistant"),

    ("Project 365, Coffee with Sketch",
     "Draw and upload a sketch every day during my coffee break; ideally should take about 10 minutes."
     "Coffee with Sketch is a daily art challenge by Sobhan Dutta built around creating and sharing one sketch each day during coffee breaks, often completed within ten minutes. The project features minimalist and experimental sketches—sometimes using coffee as a medium—and reflects themes of discipline, spontaneity, and creative exploration. Through numbered entries and recurring ideas around disposability, obligation, and fulfillment, the series captures both the practice of daily art-making and the beauty of ephemeral expression.",
     "",
     "https://www.facebook.com/CoffeeAndSketch"),

    ("YouTube Channel: BayBong Diary",
     "A very personal series sharing real, honest experiences to help others going through similar journeys. "
     "BayBong Diary blends healing, resilience, travel, and lifestyle storytelling. "
     "The channel's unique niche: Recovery + Resilience + Reflective Living.",
     "Heart Surgery & Recovery Series, Travel & Storytelling, Lifestyle & Shorts",
     "https://www.youtube.com/@baybongdiary"),

]

EDUCATION = [
    ("University of London",    "BSc Computer Science",             2018),
    ("Coursera / DeepLearning.AI", "Deep Learning Specialisation",  2021),
]


def seed():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)

        conn.execute("DELETE FROM profile")
        conn.executemany("INSERT INTO profile (key, value) VALUES (?, ?)", PROFILE)

        conn.execute("DELETE FROM skills")
        conn.executemany(
            "INSERT INTO skills (name, level, years) VALUES (?, ?, ?)", SKILLS
        )

        conn.execute("DELETE FROM experience")
        conn.executemany(
            "INSERT INTO experience (company, role, start_year, end_year, description) "
            "VALUES (?, ?, ?, ?, ?)",
            EXPERIENCE,
        )

        conn.execute("DELETE FROM projects")
        conn.executemany(
            "INSERT INTO projects (name, description, tech_stack, url) VALUES (?, ?, ?, ?)",
            PROJECTS,
        )

        conn.execute("DELETE FROM education")
        conn.executemany(
            "INSERT INTO education (institution, degree, year_graduated) VALUES (?, ?, ?)",
            EDUCATION,
        )

        conn.commit()
    print(f"Database seeded at: {DB_PATH}")


if __name__ == "__main__":
    seed()
