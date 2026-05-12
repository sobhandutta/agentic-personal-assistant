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
    ("phone",       "+1 510 402 3116"),
    ("location",    "San Jose, CA"),
    ("headline",    "Product, UX & Frontend Engineering Leader | AI-Enabled Systems Thinker | Startup Builder"),
    ("summary",     "Seasoned product, UX, and engineering leader with 20+ years of experience building scalable enterprise platforms across "
                    "B2B SaaS, AI-enabled workflows, 5G, network security, analytics, and data visualization. Combines deep frontend "
                    "engineering expertise with product thinking, UX strategy, and modern AI-assisted development practices to deliver "
                    "intelligent, scalable user experiences. Experienced in integrating AI-driven capabilities into enterprise products while "
                    "leveraging tools such as Claude Code, Claude Design, Cursor, and GitHub Copilot to accelerate development, improve code "
                    "quality, and streamline collaboration. Proven track record leading globally distributed teams, launching startup MVPs under "
                    "aggressive timelines, and bridging design, engineering, and business strategy."),
    ("key_achievements",
                    "Built and scaled UX/UI teams at startups and enterprises; launched MVPs in 4 months as a founding member, supporting successful fundraising (e.g., $26M at Elisity). "
                    "Delivered enterprise-grade security, analytics, and data products used by Fortune 500 companies. "
                    "Developed a scalable design system at Ataya, cutting development cycles by 40% and improving UX consistency. "
                    "Increased release velocity by 50% at Ataya through cross-functional alignment and frontend architecture optimization. "
                    "Drove 30% feature adoption at Elisity by embedding telemetry, UX research, and usability testing. "
                    "Launched a 0-to-1 suite of enterprise tools at Nuance (IVR Insights, DNM, ODI), generating multi-million-dollar ARR from Fortune 500 clients. "
                    "Streamlined frontend workflows using Copilot and Cursor, improving engineering throughput by 5×."),
    ("github",      "https://github.com/sobhandutta"),
    ("website",     "https://sobhandutta.myportfolio.com/about"),
    ("youtube",     "https://www.youtube.com/@baybongdiary"),
    ("languages",   "English (fluent), Bengali (native)"),
    ("availability","Open to new opportunities"),
]

SKILLS = [
    # Frontend & UI
    ("JavaScript",              "expert",        20),
    ("TypeScript",              "advanced",       8),
    ("HTML / CSS",              "expert",        20),
    ("React.js",                "expert",        15),
    ("Angular",                 "expert",        15),
    ("Redux",                   "advanced",      10),
    ("Figma",                   "expert",         7),
    # AI & Development Tools
    ("Prompt Engineering",      "advanced",       3),
    ("RAG / AI Agents",         "intermediate",   2),
    ("OpenAI APIs",             "advanced",       3),
    ("Claude Code / Claude Design", "advanced",   2),
    ("Cursor",                  "advanced",       2),
    ("GitHub Copilot",          "advanced",       3),
    ("Gradio",                  "intermediate",   1),
    # Languages & Backend
    ("Python",                  "advanced",       5),
    ("Go",                      "intermediate",   3),
    ("PostgreSQL",              "advanced",      10),
    ("MongoDB",                 "intermediate",   5),
    ("Redis",                   "intermediate",   5),
    ("Kafka",                   "intermediate",   3),
    # Cloud & Infrastructure
    ("AWS",                     "advanced",       8),
    ("Azure",                   "advanced",       5),
    ("GCP",                     "intermediate",   4),
    ("Kubernetes",              "intermediate",   4),
    ("Grafana / Prometheus",    "intermediate",   5),
]

EXPERIENCE = [
    ("Atayalan Inc",    "Director of Engineering (UX & UI)",    2022, None,
     "Founding U.S. hire responsible for building the UX and frontend engineering function from the ground up for the industry's first unified private 5G + Wi-Fi connectivity platform. "
     "Built and scaled a high-performing UX & UI team from zero, delivering the MVP in under 4 months with 100% on-time releases. "
     "Driving AI-assisted design system evolution using Claude Design, Claude Code, Cursor, and GitHub Copilot. "
     "Contributing to AI-powered product initiatives including intelligent assistants, workflow automation, and analytics-driven user experiences. "
     "Increased adoption by 35% through embedded Lean UX, Design Thinking, and product-led experimentation. "
     "Reduced development turnaround time by 5× by integrating AI-assisted tools and streamlining frontend workflows. "
     "Increased release velocity by 50% through cross-functional alignment and frontend architecture optimization."),

    ("Elisity Inc",     "Head of UX & UI Engineering",          2020, 2022,
     "Led UX and UI engineering for Elisity's cloud-native Zero Trust network security platform. "
     "Built and led a high-performing UX & UI team, delivering the company's first MVP within 3 months. "
     "Embedded end-to-end UX research and design operations, leading to a 30% improvement in task success rates. "
     "Drove product-led growth, contributing directly to Elisity securing $26M in funding within the first year. "
     "Ensured seamless handoff between design and code, improving design system adoption and reducing frontend rework by 40%."),

    ("Nuance (Microsoft)", "Principal Engineer – UX/UI Architecture", 2006, 2020,
     "Led UX strategy, architecture, and frontend development for multiple enterprise products in IVR, analytics, and big-data visualization used by Fortune 500 clients and global telecom providers. "
     "Defined and executed UX strategy across a portfolio of analytics and infrastructure tools including Nuance Insights for IVR, Unified Application Frameworks, and Nuance Application Viewer, contributing to multi-million-dollar ARR. "
     "Designed and launched 0-to-1 products such as DNM (Dial Number Manager), CS (Configuration Services), and ODI (On-Demand Insight) using React, Angular, D3.js, and Tableau. "
     "Led offshore development and design teams across a 14-year tenure spanning BeVocal → Nuance → Microsoft acquisition."),

    ("Tello Corp / Comdial / Techna International / PriceWaterhouseCoopers",
     "UI Designer & Developer",                                  2000, 2006,
     "Served as UI designer and developer across web, mobile, and desktop platforms. "
     "Led end-to-end interface design, frontend development, and interaction design. "
     "Notable project: ZCR (Zero Cost Routing), a directory-based IP calling service with cross-platform clients supporting real-time updates."),
]

PROJECTS = [
    ("Personal AI Assistant",
     "Multi-agent AI system that answers personal questions by querying SQLite, "
     "Google Drive, Gmail, and LinkedIn.",
     "Python, Anthropic Claude, Gradio, SQLite, Google APIs",
     "https://github.com/sobhandutta/personal-ai-assistant"),

    ("Project 365, Coffee with Sketch",
     "An ongoing daily art challenge: one sketch created and uploaded every day during a coffee break, each completed in approximately 10 minutes. "
     "Features abstract and expressive portraiture with circular motifs resembling coffee stains or cup rings. "
     "A notable ongoing series within the project is 'Passing Through My Own Shadow,' exploring identity and self. "
     "Reflects themes of discipline, spontaneity, disposability, and creative exploration. "
     "Sobhan is a visual artist with a Bachelor's from Govt. College of Art and Craft and a Master's in Visual Arts from Rabindra Bharati University. "
     "His work uses abstract forms, collage, and everyday disposable materials (paper, foam, fabrics, paper towels, wood). "
     "Style blends abstract, representative, and stylized art with warm hues, vibrant colors, and textured layering.",
     "Painting, Sketch, Collage, Mixed Media",
     "https://www.facebook.com/CoffeeAndSketch"),

    ("YouTube Channel: BayBong Diary",
     "A very personal series sharing real, honest experiences to help others going through similar journeys. "
     "BayBong Diary blends healing, resilience, travel, and lifestyle storytelling. "
     "The channel's unique niche: Recovery + Resilience + Reflective Living.",
     "Heart Surgery & Recovery Series, Travel & Storytelling, Lifestyle & Shorts",
     "https://www.youtube.com/@baybongdiary"),

]

EDUCATION = [
    ("Rabindra Bharati University, India",  "Master of Visual Arts",                    None),
    ("Calcutta University, India",          "Bachelor of Visual Arts",                  None),
    ("AI Engineer Core Track",              "Certification: LLM Engineering, RAG, QLoRA, Agents", None),
    ("eCornell",                            "Certification: Product Management",         None),
    ("UC Santa Cruz",                       "Certification: User-Centered Design",       None),
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
