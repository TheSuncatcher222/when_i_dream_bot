from datetime import datetime

from aiogram import (
    Router,
    F,
)
from aiogram.types import (
    FSInputFile,
    Message,
)
from jinja2 import Template
import tempfile

from app.src.crud.user import user_crud
from app.src.database.database import async_session_maker
from app.src.models.user import User
from app.src.utils.auth import IsAdmin
from app.src.utils.message import delete_messages_list
from app.src.utils.reply_keyboard import RoutersCommands

router: Router = Router()

HTML_TEMPLATE = """
<style>
    body {
        background-color: #000;
        color: #f0f0f0;
        font-family: sans-serif;
    }
        table {
        border-collapse: collapse;
        width: auto;
        table-layout: auto;
        background-color: #111;
        color: #f0f0f0;
    }
    th, td {
        border: 1px solid #444;
        padding: 5px;
        white-space: nowrap;
        text-align: center;
    }
    th {
        background-color: #222;
        font-weight: bold;
    }
    .legend p {
        margin: 0;
        line-height: 1.2;
        font-size: 14px;
        color: #ccc;
    }
    .statistic-score-width {
        width: 80px;
        text-align: center;
    }
</style>

<html>

    <head>
        <meta charset="utf-8">
        <style>
            table {
                border-collapse: collapse;
                width: auto;
                table-layout: auto;
            }
            th, td {
                border: 1px solid black;
                padding: 5px;
                white-space: nowrap;
            }
        </style>
    </head>

    <body>
        <h2>Рейтинг сновидцев ({{ datetime_now.strftime('%Y-%m-%d %H:%M') }})</h2>
        <table>
            <tr>
                <th rowspan="3">№</th>
                <th rowspan="3">Игрок</th>
                <th colspan="10">Статистика</th>
                <th colspan="8">Достижения</th>
            </tr>
            <tr>
                <th rowspan="2">🎮 Игр</th>
                <th rowspan="2">🏆 Побед</th>
                <th colspan="6">Очков</th>
                <th rowspan="2">🏃 Выходов</th>
                <th rowspan="2">📅 Последняя игра</th>
                <th rowspan="2">🦄 Сон на яву</th>
                <th rowspan="2">👹 Сущий кошмар</th>
                <th rowspan="2">🏆 Высший разум</th>
                <th rowspan="2">🕵️‍♀️ Яркие сны</th>
                <th rowspan="2">🧚‍♀️ Крестная фея</th>
                <th rowspan="2">🗿 Бу-бу-бука</th>
                <th rowspan="2">🎭 Лицемерище</th>
                <th rowspan="2">🌚 Кайфоломщик</th>
            </tr>
            <tr>
                <th class="statistic-score-width">📊 Всего</th>
                <th class="statistic-score-width">😴 Сновидец</th>
                <th class="statistic-score-width">🧚‍♀️ Фея</th>
                <th class="statistic-score-width">🗿 Бука</th>
                <th class="statistic-score-width">🎭 Песочный</th>
                <th class="statistic-score-width">🌚 Штрафов</th>
            </tr>
            {% for user in users %}
                <tr>
                    <!-- № -->
                    <td>{{ loop.index }}</td>
                    <!-- Игрок -->
                    <td>{{ user.get_full_name(hide=True) }}</td>
                    <!-- Статистика -->
                    <td>{{ user.statistics.total_games }}</td>
                    <td>{{ user.statistics.total_wins }}</td>
                    <td>{{ user.statistics.top_score }}</td>
                    <td>{{ user.statistics.top_score_dreamer }}</td>
                    <td>{{ user.statistics.top_score_fairy }}</td>
                    <td>{{ user.statistics.top_score_buka }}</td>
                    <td>{{ user.statistics.top_score_sandman }}</td>
                    <td>{{ user.statistics.top_penalties }}</td>
                    <td>{{ user.statistics.total_quits }}</td>
                    <td>{{ user.statistics.last_game_datetime.strftime("%d.%m.%Y") if user.statistics.last_game_datetime else "-" }}</td>
                    <!-- Достижения -->
                    <td>{{ user.achievements.dream_master }}</td>
                    <td>{{ user.achievements.nightmare }}</td>
                    <td>{{ user.achievements.top_score }}</td>
                    <td>{{ user.achievements.top_score_dreamer }}</td>
                    <td>{{ user.achievements.top_score_fairy }}</td>
                    <td>{{ user.achievements.top_score_buka }}</td>
                    <td>{{ user.achievements.top_score_sandman }}</td>
                    <td>{{ user.achievements.top_penalties }}</td>
                </tr>
            {% endfor %}
        </table>

        <br>

        <div class="legend">
            <p>🦄 Сон на яву: верно угадал(а) все слова и пересказал(а) сон</p>
            <p>👹 Сущий кошмар: не угадал(а) ни одного слова</p>
            <p>🏆 Высший разум: получил(а) больше всего очков</p>
            <p>🕵️‍♀️ Яркие сны: получил(а) больше всего очков за сновидца</p>
            <p>🧚‍♀️ Крестная фея: получил(а) больше всего очков за фею</p>
            <p>🗿 Бу-бу-бука: получил(а) больше всего очков за буку</p>
            <p>🎭 Лицемерище: получил(а) больше всего очков за песочного человечка</p>
            <p>🌚 Кайфоломщик: получил(а) больше всего штрафных очков</p>
        </div>

    </body>
</html>
"""


@router.message(
    IsAdmin(),
    F.text == RoutersCommands.STATISTIC,
)
async def statistic(message: Message):
    """
    Обрабатывает команду "Статистика".
    """
    await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))

    async with async_session_maker() as session:
        users: list[User] = await user_crud.retrieve_players_statistic(session=session)

    datetime_now: str = datetime.now()

    html_content : str = __render_template(datetime_now=datetime_now, users=users)
    with tempfile.NamedTemporaryFile('w+', suffix='.html', delete=False) as tmp:
        tmp.write(html_content)
        tmp.flush()
        file: FSInputFile = FSInputFile(tmp.name, filename=f"рейтинг_сновидцев_{datetime_now.strftime('%Y_%m_%d_%H_%M_%S')}.html")

    await message.answer_document(document=file)


def __render_template(users: list[User], datetime_now: str) -> str:
    """Рендерит HTML страницу."""
    template: Template = Template(HTML_TEMPLATE)
    return template.render(datetime_now=datetime_now, users=users)
