"""
Модуль с вспомогательными функциями для извлечения и сохранения данных в Redis.

Использование хранилища Redis для ручного извлечения и сохранения данных
осуществляется через функции redis_get и redis_set соответственно.
"""

import json

from app.src.database.database import redis_engine


def redis_check_exists(key: str) -> bool:
    """
    Проверяет существование ключа в Redis.
    """
    return redis_engine.exists(key)


def redis_delete(key: str) -> None:
    """
    Удаляет данные из Redis по указанному ключу.
    """
    redis_engine.delete(key)


def redis_flushall() -> None:
    """
    Удаляет все данные из Redis.
    """
    redis_engine.flushall()


def redis_get(
    key: str,
    get_ttl: bool = False,
    default: any = None,
) -> any:
    """
    Извлекает данные из Redis по указанному ключу в типах данных Python.
    Если данных нет, то возвращает default.

    Если get_ttl=True, то возвращается TTL в секундах (-1, если ключа не существует).
    """
    data: any = redis_engine.get(name=key)
    if data is not None:
        try:
            data: any = json.loads(s=data)
        except json.JSONDecodeError:
            pass
    elif default is not None:
        data: any = default

    if get_ttl:
        return data, redis_engine.ttl(name=key)
    return data


def redis_get_ttl(key: str) -> int:
    """
    Извлекает TTL из Redis по указанному ключу
    (-1, если ключа не существует).
    """
    return redis_engine.ttl(name=key)


def redis_set(key: str, value: any, ex_sec: int | None = None) -> None:
    """
    Сохраняет данные в Redis по указанному ключу.

    Преобразует тип данных dict в JSON.
    """
    redis_engine.set(
        name=key,
        value=(
            json.dumps(value)
            if isinstance(value, (dict, list, tuple, int, float, bool, type(None)))
            else value
        ),
        ex=ex_sec,
    )
