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
    .legend p {
        margin: 0;
        line-height: 1.2;
        font-size: 14px;
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
        <h2>Рейтинг сновидцев</h2>
        <table>
            <tr>
                <th>№</th>
                <th>Name</th>

                <th>🏆 Высший разум</th>
                <th>🥇 Победитель</th>
                <th>🏃 Гипнофоб </th>
                <th>🌚 Кайфоломщик</th>
                <th>🕵️‍♀️ Яркие сны</th>
                <th>🧚‍♀️ Крестная фея</th>
                <th>🗿 Бу-бу-бука</th>
                <th>🎭 Лицемерище</th>
                <th>😻 Cон на яву</th>
                <th>👺 Cущий кошмар</th>

                <th>📅 Последняя игра</th>
            </tr>
            {% for user in users %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ user.get_full_name(hide=True) }}</td>

                    <td>{{ user.statistics.top_score }}</td>
                    <td>{{ user.statistics.total_wins }}</td>
                    <td>{{ user.statistics.total_quits }}</td>
                    <td>{{ user.statistics.top_penalties }}</td>
                    <td>{{ user.statistics.top_score_dreamer }}</td>
                    <td>{{ user.statistics.top_score_fairy }}</td>
                    <td>{{ user.statistics.top_score_buka }}</td>
                    <td>{{ user.statistics.top_score_sandman }}</td>
                    <td>{{ user.statistics.dream_master }}</td>
                    <td>{{ user.statistics.nightmare }}</td>

                    <td>{{ user.statistics.last_game_datetime.strftime("%d.%m.%Y") if user.statistics.last_game_datetime else "-" }}</td>
                </tr>
            {% endfor %}
        </table>

        <br>

        <div class="legend">
            <p>😻 Сон наяву: отгадал(а) все слова за сновидца и верно пересказал(а) сон</p>
            <p>👺 Сущий кошмар: не отгадал(а) ни одного слова за сновидца</p>
            <p>🌚 Кайфоломщик: получил(а) больше всего штрафных очков</p>
            <p>🏆 Высший разум: получил(а) больше всего очков</p>
            <p>🗿 Бу-бу-бука: получил(а) больше всего очков за буку</p>
            <p>🧚‍♀️ Крестная фея: получил(а) больше всего очков за фею</p>
            <p>🎭 Лицемерище: получил(а) больше всего очков за песочного человечка</p>
            <p>🕵️‍♀️ Яркие сны: получил(а) больше всего очков за сновидца</p>
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

    html_content : str = __render_template(users=users)
    with tempfile.NamedTemporaryFile('w+', suffix='.html', delete=False) as tmp:
        tmp.write(html_content)
        tmp.flush()
        file: FSInputFile = FSInputFile(tmp.name, filename="рейтинг_сновидцев.html")

    await message.answer_document(document=file)


def __render_template(users: list[User]) -> str:
    """Рендерит HTML страницу."""
    template: Template = Template(HTML_TEMPLATE)
    return template.render(users=users)
