import logging
import os
import requests
import sys
import time
import telegram
from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка наличия токенов."""
    tokens = (
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
    )
    return all(tokens)


def send_message(bot, message):
    """Отправка сообщений в Telegram."""
    try:
        logging.info('Отправка сообщения')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено')
    except telegram.error.TelegramError as e:
        logging.error(f'Не удалось отправить сообщение {e}')
        raise Exception('Не удалось отправить сообщение в Телеграмм')


def get_api_answer(timestamp):
    """Запрос к эндпоиниту."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception as e:
        logging.error(f'Недоступность эндпоинта, ошибка: {e}')
        raise Exception('Недоступность эндпоинта')
    if response.status_code != HTTPStatus.OK:
        logging.error(f'Не удалось получить ответ от API,'
                      f'код ошибки {response.status_code}')
        raise Exception(response.status_code)
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип ответа API')
    if 'homeworks' not in response:
        logging.error("Отсутствие 'homeworks' в ответе API")
        raise KeyError('Отсутствие ожидаемых ключей')
    if 'current_date' not in response:
        logging.error("Отсутствие 'current_date' в ответе API")
        raise KeyError('Отсутствие ожидаемых ключей')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError("Неверный тип 'homeworks'")
    return response.get('homeworks'), response.get('current_date')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    try:
        homework_name, homework_status = (
            homework['homework_name'], homework['status']
        )
    except KeyError:
        raise KeyError("Нет ожидаемого ключа")
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        logging.error('Неожиданный статус домашней работы в ответе API')
        raise KeyError('Нет нужного статуса')


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        level=logging.DEBUG,
        filename='log.log',
        format='%(asctime)s, %(levelname)s, %(message)s'
    )
    if not check_tokens():
        logging.critical('Не указан токен')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            logging.info('Получили ответ от API')
            homeworks, current_time = check_response(response)
            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
            else:
                logging.debug('Отсутствует новая информация')
            timestamp = current_time
            logging.info('Повторный запрос через 10 минут')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
            raise Exception(error)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
