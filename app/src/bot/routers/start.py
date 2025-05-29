from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import (
    InputMediaPhoto,
    Message,
)

from app.src.crud.user import user_crud
from app.src.database.database import async_session_maker
from app.src.utils.image import get_rules_ids_telegram
from app.src.utils.message import delete_messages_list
from app.src.utils.reply_keyboard import get_keyboard_main_menu

if TYPE_CHECKING:
    from app.src.models.user import User

router: Router = Router()


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    """
    Обрабатывает команду /start и регистрирует/обновляет пользователя.
    """
    answer: Message = await message.answer(
        text=(
            'Добро пожаловать, о чудесный сновидец!'
            '\n\n'
            'Сегодня ты отправляешься в невероятное путешествие по миру снов. Миру, '
            'где обитают сказочные создания, вершится магия и процветает фантазия. '
            'Там ты встретишь друзей и врагов, правдолюбов и лжецов, людей искренних '
            'и лицемерных.'
            '\n\n'
            'Чтобы успешно пройти через все испытания тебе нужно проявить смелость, '
            'находчивость, смекалку и внутреннюю интуицию. Желаю приятных снов!'
        ),
        reply_markup=get_keyboard_main_menu(user_id_telegram=message.from_user.id),
    )
    await message.answer_media_group(
        media=[
            InputMediaPhoto(media=media_id)
            for media_id
            in await get_rules_ids_telegram()
        ],
    )

    async with async_session_maker() as session:
        user: User | None = await user_crud.retrieve_by_id_telegram(
            obj_id_telegram=message.from_user.id,
            session=session,
        )
        messages_ids: list[int] = [message.message_id]

        if not user:
            user: User = await user_crud.create(
                obj_data={
                    'id_telegram': str(message.from_user.id),
                    'message_main_last_id': answer.message_id,
                    'name_first': message.from_user.first_name,
                    'name_last': message.from_user.last_name,
                    'username': message.from_user.username,
                },
                session=session,
                perform_commit=False,
            )
        elif user.message_main_last_id:
            messages_ids: list[int] = list(range(user.message_main_last_id, message.message_id + 1))

        await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=messages_ids,
        )
        await user_crud.update_by_id(
            obj_id=user.id,
            obj_data={
                'datetime_stop': None,
                'is_stopped_bot': False,
                'message_main_last_id': answer.message_id,
                'name_first': message.from_user.first_name,
                'name_last': message.from_user.last_name,
                'username': message.from_user.username,
            },
            session=session,
        )
