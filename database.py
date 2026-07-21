import sqlite3
from datetime import datetime

DB_NAME = "stories.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Таблица готовых вариантов: Категории сказок
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            prompt_tail TEXT NOT NULL
        )
    """)

    # Таблица готовых вариантов: Национальности / этностили
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nationalities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            prompt_tail TEXT NOT NULL
        )
    """)

    # Таблица готовых вариантов: Морали (чему учит сказка)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS morals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            prompt_tail TEXT NOT NULL
        )
    """)

    # Основная таблица: Сказки
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme TEXT NOT NULL,
            age TEXT,
            hero_name TEXT,
            category_id INTEGER,
            nationality_id INTEGER,
            moral_id INTEGER,
            story_text TEXT NOT NULL,
            summary TEXT,
            created_at TEXT NOT NULL,
            is_favorite INTEGER DEFAULT 0,
            note TEXT DEFAULT '',
            read_count INTEGER DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (nationality_id) REFERENCES nationalities (id),
            FOREIGN KEY (moral_id) REFERENCES morals (id)
        )
    """)

    conn.commit()

    # Заполняем категории значениями по умолчанию, если таблица пустая
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        default_categories = [
            ("Обычная сказка", ""),
            ("Сказка-притча", "В конце сказки обязательно добавь мораль — короткий вывод, чему учит эта история."),
            ("Сказка о животных", "Главными героями должны быть животные, наделённые человеческими чертами характера."),
            ("Фантастическая сказка", "Действие происходит в фантастическом мире — космос, другие планеты, добрые роботы, звездолёты. Но сохраняй мягкий, убаюкивающий тон и уютный финал."),
        ]
        cursor.executemany(
            "INSERT INTO categories (name, prompt_tail) VALUES (?, ?)",
            default_categories
        )

    # Заполняем национальности значениями по умолчанию, если таблица пустая
    cursor.execute("SELECT COUNT(*) FROM nationalities")
    if cursor.fetchone()[0] == 0:
        default_nationalities = [
            ("Украинская", "Используй украинские имена героев (например: Тарас, Оксана, Марійка), упоминай украинские традиции и природу."),
            ("Грузинская", "Используй грузинские имена героев (например: Гиорги, Нино, Дато), упоминай грузинские традиции — горы, гостеприимство, застолье."),
            ("Восточная", "Пиши в стиле восточных сказок (как «Тысяча и одна ночь») — используй восточные имена, упоминай базары, дворцы, пустыню."),
            ("Английская", "Используй английские имена героев (например: Джек, Эмили), упоминай традиции английской деревни, туман, старинные замки."),
            ("Португальская", "Используй португальские имена героев (например: Жоао, Мария), упоминай море, рыбацкие деревни."),
        ]
        cursor.executemany(
            "INSERT INTO nationalities (name, prompt_tail) VALUES (?, ?)",
            default_nationalities
        )

    # Заполняем морали значениями по умолчанию, если таблица пустая
    cursor.execute("SELECT COUNT(*) FROM morals")
    if cursor.fetchone()[0] == 0:
        default_morals = [
            ("Не важно, пусть ИИ придумает сам", ""),
            ("О дружбе", "Сказка должна учить ребёнка ценности дружбы и взаимопомощи."),
            ("О честности", "Сказка должна показывать, почему важно говорить правду."),
            ("О дисциплине", "Сказка должна показывать пользу дисциплины и порядка."),
            ("Думать о других, не только о себе", "Сказка должна учить заботе об окружающих, а не только о своих желаниях."),
            ("К чему приводит глупость/легкомыслие", "Сказка должна на добром примере показать последствия необдуманных поступков."),
            ("О смелости, преодолении страха", "Сказка должна учить ребёнка справляться со страхами и быть смелым."),
            ("О доброте", "Сказка должна показывать силу доброты и отзывчивости."),
            ("О терпении", "Сказка должна учить ребёнка терпению и умению ждать."),
        ]
        cursor.executemany(
            "INSERT INTO morals (name, prompt_tail) VALUES (?, ?)",
            default_morals
        )

    conn.commit()
    conn.close()


# --- Таблицы готовых вариантов ---

def get_categories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, prompt_tail FROM categories")
    result = cursor.fetchall()
    conn.close()
    return result


def get_nationalities():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, prompt_tail FROM nationalities")
    result = cursor.fetchall()
    conn.close()
    return result


def get_morals():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, prompt_tail FROM morals")
    result = cursor.fetchall()
    conn.close()
    return result


# --- Работа со сказками ---

def save_story(theme, age, hero_name, category_id, nationality_id, moral_id, story_text, summary):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO stories (
            theme, age, hero_name, category_id, nationality_id, moral_id,
            story_text, summary, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        theme, age, hero_name, category_id, nationality_id, moral_id,
        story_text, summary, datetime.now().isoformat()
    ))
    conn.commit()
    story_id = cursor.lastrowid
    conn.close()
    return story_id


def get_stories_list(only_favorites=False):
    """Короткий список сказок для выпадающего меню."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT id, theme, hero_name, created_at, is_favorite, read_count FROM stories"
    if only_favorites:
        query += " WHERE is_favorite = 1"
    query += " ORDER BY id DESC"

    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    return result


def get_story(story_id):
    """Полные данные одной сказки вместе с названиями из таблиц готовых вариантов."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            s.id, s.theme, s.age, s.hero_name,
            c.name, n.name, m.name,
            s.story_text, s.summary, s.created_at,
            s.is_favorite, s.note, s.read_count
        FROM stories s
        LEFT JOIN categories c ON s.category_id = c.id
        LEFT JOIN nationalities n ON s.nationality_id = n.id
        LEFT JOIN morals m ON s.moral_id = m.id
        WHERE s.id = ?
    """, (story_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    keys = [
        "id", "theme", "age", "hero_name",
        "category", "nationality", "moral",
        "story_text", "summary", "created_at",
        "is_favorite", "note", "read_count",
    ]
    return dict(zip(keys, row))


def increment_read_count(story_id):
    """+1 к счётчику прочтений — когда родитель открывает сказку."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE stories SET read_count = read_count + 1 WHERE id = ?",
        (story_id,)
    )
    conn.commit()
    conn.close()


def set_favorite(story_id, is_favorite):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE stories SET is_favorite = ? WHERE id = ?",
        (1 if is_favorite else 0, story_id)
    )
    conn.commit()
    conn.close()


def set_note(story_id, note):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE stories SET note = ? WHERE id = ?",
        (note, story_id)
    )
    conn.commit()
    conn.close()


def delete_story(story_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stories WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()
