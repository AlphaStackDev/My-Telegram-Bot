import asyncio
import asyncpg

DB_CONFIG = {
    "host": "localhost",
    "user": "postgres",
    "password": "Alpha.com002",
    "database": "unical_bot",
}

# -----------------
# 1) Add courses
# -----------------
NEW_COURSES = [
    ("INTRODUCTION TO MICROECONOMICS", "ECO202"),
    ("INTRODUCTION TO MACROECONOMICS", "ECO204"),
    ("STATISTICS FOR ECONOMISTS", "ECO206"),
    ("LABOUR ECONOMICS", "ECO208"),
    ("INTRODUCTION TO CAPITAL MARKET II", "ECO210"),
    ("DEMOGRAPHY", "ECO214"),
    ("ENTREPRENURSHIP AND INNOVATION", "ENT211"),
    ("COMPUTER APPLICATIONS", "GSS212"),
    ("PHILOSOPHY, LOGIC AND HUMAN EXISTENCE", "GST212"),
]

# -----------------------------
# 2) Link question papers to courses
# -----------------------------
# Map Course Code -> exact PDF filename in your folder
FILE_MAP = {
    "ECO202": "MICROECONOMIC THEORY (ECO 202).pdf",
    "ECO204": "MACROECONOMICS (ECO 204).pdf",
    "ECO206": "STATISTICS FOR ECONOMICS (ECO 206).pdf",
    "ECO210": "CAPITAL MARKET (ECO 210).pdf",
    "ECO222": "MACROECONOMICS (ECO 222).pdf",
}

# If your question_papers.file_url is expected to be a filesystem path or a URL,
# keep it as the filename for now (like your current bot does with os.path.join).
# Update these values if your DB expects a full relative/absolute path.


async def upsert_courses(conn: asyncpg.Connection) -> None:
    query = """
    INSERT INTO courses (course_title, course_code)
    VALUES ($1, $2)
    ON CONFLICT (course_code) DO UPDATE
    SET course_title = EXCLUDED.course_title;
    """

    for title, code in NEW_COURSES:
        await conn.execute(query, title, code)
        print(f"Upserted course: {code} - {title}")


async def link_question_papers(conn: asyncpg.Connection) -> None:
    for code, filename in FILE_MAP.items():
        course = await conn.fetchrow(
            "SELECT id FROM courses WHERE course_code = $1",
            code,
        )
        if not course:
            print(f"[SKIP] Course {code} not found in database.")
            continue

        course_id = course["id"]

        # Avoid duplicates: if question_papers already has a row for this course_id + file_url, skip.
        # If your schema doesn't have a unique constraint, we just check manually.
        exists = await conn.fetchrow(
            "SELECT id FROM question_papers WHERE course_id = $1 AND file_url = $2 LIMIT 1",
            course_id,
            filename,
        )
        if exists:
            print(f"[SKIP] question_papers already linked for {code}: {filename}")
            continue

        await conn.execute(
            """
            INSERT INTO question_papers (course_id, paper_title, file_url)
            VALUES ($1, $2, $3)
            """,
            course_id,
            f"Past Question: {code}",
            filename,
        )
        print(f"Linked: {filename} -> {code}")


async def main() -> None:
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await upsert_courses(conn)
        await link_question_papers(conn)
        print("Done ✅")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

conn = await asyncpg.connect(**DB_CONFIG)
print(f"Connected to database: {conn.get_server_version()}")