import base64
import os

import httpx
from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.exceptions import (
    AuthenticationError,
    BadRequestError,
    ForbiddenError,
    GigaChatException,
    NotFoundError,
    RateLimitError,
    RequestEntityTooLargeError,
    ServerError,
    UnprocessableEntityError,
)

# ищем .env рядом с модулем, чтобы запуск работал из любой папки
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

MAX_INPUT_LENGTH = 1000
DEFAULT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat-3-Pro")

USER_MESSAGES = {
    "bad_access": "Не настроен доступ к сервису.",
    "unavailable": "Сервис временно недоступен. Попробуйте позже.",
    "network": "Не удалось получить ответ. Попробуйте ещё раз.",
    "empty_response": "Пустой ответ модели. Попробуйте переформулировать вопрос.",
}

SYSTEM_PROMPT = (
    "Ты — ассистент по составлению списка покупок. Составь список продуктов "
    "для указанного блюда на указанное количество человек. Каждый продукт — "
    "отдельной строкой, с количеством, если это уместно.\n"
    "Если формат «Список продуктов» — в ответе ТОЛЬКО перечень продуктов, "
    "без шагов приготовления и без пояснений.\n"
    "Если формат «Список + шаги» — сначала перечень продуктов (каждый на "
    "своей строке), затем краткие шаги приготовления: ровно 5–8 нумерованных "
    "пунктов. Больше ни о чём не пиши."
)


class ApiError(Exception):
    """Ошибка API с готовым сообщением для пользователя."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def build_messages(dish: str, people: str, format_: str) -> list[dict]:
    user_text = f"Блюдо: {dish}\nКоличество человек: {people}\nФормат: {format_}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]


def _make_client() -> GigaChat:
    client_id = os.getenv("GIGACHAT_CLIENT_ID")
    secret = os.getenv("GIGACHAT_SECRET")
    if not (client_id and secret):
        raise ApiError(USER_MESSAGES["bad_access"])

    # SDK Gigachat принимает только авторизационный ключ в формате base64
    # (client_id:secret), поэтому собираем его здесь, а не вручную в .env
    credentials = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    return GigaChat(
        credentials=credentials,
        verify_ssl_certs=False,  # учебный проект; на проде — свой CA bundle
        timeout=30,
    )


def _extract_content(response) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        raise ApiError(USER_MESSAGES["empty_response"])
    if not content or not content.strip():
        raise ApiError(USER_MESSAGES["empty_response"])
    return content.strip()


def generate_shopping_list(dish: str, people: str, format_: str) -> str:
    """Возвращает список покупок или бросает ApiError с готовым сообщением."""
    messages = build_messages(dish, people, format_)
    client = _make_client()

    # 4xx повторять нет смысла; 5xx/429 и таймаут — максимум 1 повтор
    attempts = 2
    for attempt in range(attempts):
        try:
            response = client.chat({
                "model": DEFAULT_MODEL,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024,
            })
        except ApiError:
            raise
        except (AuthenticationError, BadRequestError, ForbiddenError,
                NotFoundError, UnprocessableEntityError, RequestEntityTooLargeError):
            raise ApiError(USER_MESSAGES["bad_access"])
        except (ServerError, RateLimitError):
            if attempt < attempts - 1:
                continue
            raise ApiError(USER_MESSAGES["unavailable"])
        except GigaChatException:
            # любые прочие ошибки API (в т.ч. сломанный ответ) — без деталей
            raise ApiError(USER_MESSAGES["network"])
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError):
            if attempt < attempts - 1:
                continue
            raise ApiError(USER_MESSAGES["network"])
        except Exception:
            # гарантия того, что в интерфейс не уйдёт сырое исключение
            raise ApiError(USER_MESSAGES["network"])

        return _extract_content(response)

    raise ApiError(USER_MESSAGES["network"])