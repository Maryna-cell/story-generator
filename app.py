import os
import json
import gradio as gr
from openai import OpenAI
from dotenv import load_dotenv
from database import (
    init_db,
    get_categories, get_nationalities, get_morals,
    save_story, get_stories_list, get_story,
    increment_read_count, set_favorite, set_note, delete_story,
)

# --- Это бэкенд: логика обращения к искусственному интеллекту ---

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

with open("prompt.txt", "r", encoding="utf-8") as file:
    base_prompt = file.read()

# Готовим базу данных при старте приложения
init_db()

# Загружаем таблицы готовых вариантов один раз при старте
categories_by_name = {name: (cat_id, tail) for cat_id, name, tail in get_categories()}
nationalities_by_name = {name: (nat_id, tail) for nat_id, name, tail in get_nationalities()}
morals_by_name = {name: (moral_id, tail) for moral_id, name, tail in get_morals()}


def create_story(theme, age, hero_name, category_name, nationality_name, moral_name):
    category_id, category_tail = categories_by_name[category_name]
    nationality_id, nationality_tail = nationalities_by_name[nationality_name]
    moral_id, moral_tail = morals_by_name[moral_name]

    # Собираем финальную инструкцию для ИИ из нескольких кусков
    full_prompt = base_prompt
    if category_tail:
        full_prompt += "\n\n" + category_tail
    if nationality_tail:
        full_prompt += "\n\n" + nationality_tail

    moral_instruction = ""
    if moral_tail:
        moral_instruction = f"\nВАЖНО: {moral_tail}"

    user_request = (
        f"Сочини сказку на тему: {theme}. "
        f"Возраст ребёнка: {age}. "
        f"Главного героя зовут: {hero_name}."
        f"{moral_instruction}\n\n"
        f"Ответь строго в формате JSON без пояснений и без markdown-обрамления, с двумя полями:\n"
        f'{{"story": "текст самой сказки", "summary": "если это сказка-притча — мораль истории, '
        f'иначе — краткое описание в одно предложение, о чём эта сказка"}}'
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": full_prompt},
            {"role": "user", "content": user_request}
        ]
    )

    raw_answer = response.choices[0].message.content.strip()

    # ИИ иногда оборачивает JSON в ```json ... ``` — на всякий случай очищаем
    if raw_answer.startswith("```"):
        raw_answer = raw_answer.strip("`")
        raw_answer = raw_answer.replace("json", "", 1).strip()

    try:
        parsed = json.loads(raw_answer)
        story_text = parsed.get("story", raw_answer)
        summary = parsed.get("summary", "")
    except json.JSONDecodeError:
        story_text = raw_answer
        summary = ""

    save_story(theme, age, hero_name, category_id, nationality_id, moral_id, story_text, summary)

    # Обновляем выпадающий список на вкладке «Мои сказки»,
    # чтобы новая сказка появилась там сразу
    return story_text, summary, gr.update(choices=build_choices())


# --- Логика вкладки «Мои сказки» ---

def build_choices(only_favorites=False):
    """Готовит список для выпадающего меню: (что видит человек, id сказки)."""
    rows = get_stories_list(only_favorites=only_favorites)
    choices = []
    for story_id, theme, hero_name, created_at, is_favorite, read_count in rows:
        date_part = created_at[:10] if created_at else ""
        star = "⭐ " if is_favorite else ""
        hero_part = f" ({hero_name})" if hero_name else ""
        reads_part = f" · прочитано: {read_count}" if read_count else ""
        label = f"{star}#{story_id} — {theme}{hero_part} · {date_part}{reads_part}"
        choices.append((label, story_id))
    return choices


def refresh_list(only_favorites):
    return gr.update(choices=build_choices(only_favorites), value=None)


def open_story(story_id):
    """Открывает сказку: показывает текст и увеличивает счётчик прочтений."""
    if not story_id:
        return "", "", "", False, "", gr.update()

    increment_read_count(story_id)
    story = get_story(story_id)

    if story is None:
        return "Сказка не найдена.", "", "", False, "", gr.update()

    info = (
        f"**Тема:** {story['theme']}  \n"
        f"**Возраст:** {story['age']}  \n"
        f"**Герой:** {story['hero_name']}  \n"
        f"**Категория:** {story['category']}  \n"
        f"**Колорит:** {story['nationality']}  \n"
        f"**Мораль:** {story['moral']}  \n"
        f"**Создана:** {story['created_at'][:16].replace('T', ' ')}  \n"
        f"**Прочитано раз:** {story['read_count']}"
    )

    return (
        story["story_text"],
        story["summary"] or "",
        info,
        bool(story["is_favorite"]),
        story["note"] or "",
        gr.update(),
    )


def toggle_favorite(story_id, is_favorite, only_favorites):
    if not story_id:
        return gr.update(), "Сначала выбери сказку."
    set_favorite(story_id, is_favorite)
    msg = "Добавлено в избранное ⭐" if is_favorite else "Убрано из избранного"
    return gr.update(choices=build_choices(only_favorites)), msg


def save_note(story_id, note_text):
    if not story_id:
        return "Сначала выбери сказку."
    set_note(story_id, note_text)
    return "Заметка сохранена ✍️"


def remove_story(story_id, only_favorites):
    if not story_id:
        return gr.update(), "Сначала выбери сказку.", "", "", "", False, ""
    delete_story(story_id)
    return (
        gr.update(choices=build_choices(only_favorites), value=None),
        "Сказка удалена 🗑️",
        "", "", "", False, "",
    )


# --- Это фронтенд: красивое окно, которое видит пользователь ---

with gr.Blocks(title="🌙 Генератор сказок на ночь") as demo:
    gr.Markdown("# 🌙 Генератор сказок на ночь")

    with gr.Tab("Создать новую сказку"):
        gr.Markdown("Заполни поля — и получи персональную сказку для своего ребёнка.")

        with gr.Row():
            with gr.Column():
                theme_input = gr.Textbox(label="О чём будет сказка?", placeholder="например: про доброго ёжика")
                age_input = gr.Textbox(label="Возраст ребёнка", placeholder="например: 5 лет")
                hero_input = gr.Textbox(label="Имя главного героя", placeholder="например: Тимка")
                category_input = gr.Dropdown(
                    label="Категория сказки",
                    choices=list(categories_by_name.keys()),
                    value="Обычная сказка",
                    filterable=False,
                )
                nationality_input = gr.Dropdown(
                    label="Национальный колорит",
                    choices=list(nationalities_by_name.keys()),
                    value="Украинская",
                    filterable=False,
                )
                moral_input = gr.Dropdown(
                    label="Чему должна научить сказка?",
                    choices=list(morals_by_name.keys()),
                    value="Не важно, пусть ИИ придумает сам",
                    filterable=False,
                )
                create_btn = gr.Button("Создать сказку", variant="primary")

            with gr.Column():
                story_output = gr.Textbox(label="Твоя сказка", lines=20)
                summary_output = gr.Textbox(label="Мораль / краткое описание", lines=3)

    with gr.Tab("Мои сказки"):
        gr.Markdown("Здесь хранятся все созданные сказки — можно открыть и прочитать снова.")

        with gr.Row():
            favorites_only = gr.Checkbox(label="Только избранные ⭐", value=False)
            refresh_btn = gr.Button("Обновить список 🔄")

        stories_dropdown = gr.Dropdown(
            label="Выбери сказку",
            choices=build_choices(),
            value=None,
            filterable=False,
        )
        open_btn = gr.Button("Открыть и прочитать", variant="primary")

        status_msg = gr.Markdown("")

        with gr.Row():
            with gr.Column(scale=2):
                saved_story_output = gr.Textbox(label="Текст сказки", lines=20)
            with gr.Column(scale=1):
                saved_info = gr.Markdown("")
                saved_summary = gr.Textbox(label="Мораль / краткое описание", lines=3)
                favorite_checkbox = gr.Checkbox(label="Любимая сказка ⭐", value=False)
                note_input = gr.Textbox(
                    label="Заметка",
                    placeholder="например: Тимка просит каждый вечер",
                    lines=2,
                )
                save_note_btn = gr.Button("Сохранить заметку")
                delete_btn = gr.Button("Удалить сказку 🗑️")

    # --- Связываем кнопки с функциями ---

    create_btn.click(
        fn=create_story,
        inputs=[theme_input, age_input, hero_input, category_input, nationality_input, moral_input],
        outputs=[story_output, summary_output, stories_dropdown],
    )

    refresh_btn.click(
        fn=refresh_list,
        inputs=[favorites_only],
        outputs=[stories_dropdown],
    )

    favorites_only.change(
        fn=refresh_list,
        inputs=[favorites_only],
        outputs=[stories_dropdown],
    )

    open_btn.click(
        fn=open_story,
        inputs=[stories_dropdown],
        outputs=[saved_story_output, saved_summary, saved_info, favorite_checkbox, note_input, status_msg],
    )

    favorite_checkbox.change(
        fn=toggle_favorite,
        inputs=[stories_dropdown, favorite_checkbox, favorites_only],
        outputs=[stories_dropdown, status_msg],
    )

    save_note_btn.click(
        fn=save_note,
        inputs=[stories_dropdown, note_input],
        outputs=[status_msg],
    )

    delete_btn.click(
        fn=remove_story,
        inputs=[stories_dropdown, favorites_only],
        outputs=[
            stories_dropdown, status_msg, saved_story_output,
            saved_summary, saved_info, favorite_checkbox, note_input,
        ],
    )

demo.launch(theme=gr.themes.Soft(), server_name="0.0.0.0", server_port=7860)
