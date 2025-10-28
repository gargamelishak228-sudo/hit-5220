"""Обработчики команд и сообщений бота."""

import logging
from aiogram import Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from keyboards import (
    get_main_menu_keyboard,
    get_translation_type_keyboard,
    get_share_keyboard,
    get_history_keyboard,
    get_cancel_keyboard
)
from slang_service import slang_service
from states import TranslationStates

logger = logging.getLogger(__name__)

# История переводов (в реальном проекте лучше использовать базу данных)
translation_history = {}


def register_handlers(dp: Dispatcher) -> None:
    """Регистрирует все обработчики."""
    
    # Команды
    dp.message.register(start_command, CommandStart())
    
    # Callback queries
    dp.callback_query.register(translation_menu, lambda c: c.data == "translation_menu")
    dp.callback_query.register(start_slang_to_normal, lambda c: c.data == "translate_slang_to_normal")
    dp.callback_query.register(start_normal_to_slang, lambda c: c.data == "translate_normal_to_slang")
    dp.callback_query.register(process_translation, TranslationStates.waiting_for_text)
    dp.callback_query.register(show_history, lambda c: c.data == "history_menu")
    dp.callback_query.register(show_history_item, lambda c: c.data.startswith("history_item_"))
    dp.callback_query.register(random_slang, lambda c: c.data == "random_word")
    dp.callback_query.register(start_search, lambda c: c.data == "search_menu")
    dp.callback_query.register(process_search, TranslationStates.waiting_for_search)
    dp.callback_query.register(help_command, lambda c: c.data == "help_menu")
    dp.callback_query.register(cancel_command, lambda c: c.data == "cancel")
    dp.callback_query.register(back_to_main, lambda c: c.data == "back_to_main")
    dp.callback_query.register(translate_again, lambda c: c.data == "translate_again")
    
    # Сообщения
    dp.message.register(process_translation, TranslationStates.waiting_for_text)
    dp.message.register(process_search, TranslationStates.waiting_for_search)
    dp.message.register(cancel_message, lambda message: message.text == "Отмена")
    dp.message.register(handle_unknown_message)


async def start_command(message: Message):
    """Обработчик команды /start."""
    welcome_text = """
Добро пожаловать в SlangTranslate?

Я помогу тебе:
- Переводить текст со сленга на обычный язык
- Изучать значения сленговых слов
- Искать слова по значению

Выбери действие в меню ниже!
"""
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard()
    )


async def translation_menu(callback: CallbackQuery):
    """Обработчик кнопки перевода текста."""
    await callback.message.edit_text(
        "Выбери тип перевода:",
        reply_markup=get_translation_type_keyboard()
    )


async def start_slang_to_normal(callback: CallbackQuery, state: FSMContext):
    """Начинает перевод со сленга на обычный."""
    await callback.message.edit_text(
        "Отправь мне текст со сленга, который нужно перевести на обычный язык:",
        reply_markup=None
    )
    await state.set_state(TranslationStates.waiting_for_text)
    await state.update_data(translation_type="slang_to_normal")


async def start_normal_to_slang(callback: CallbackQuery, state: FSMContext):
    """Начинает перевод с обычного на сленг."""
    await callback.message.edit_text(
        "Отправь мне обычный текст, который нужно перевести на сленг:",
        reply_markup=None
    )
    await state.set_state(TranslationStates.waiting_for_text)
    await state.update_data(translation_type="normal_to_slang")


async def process_translation(message: Message, state: FSMContext):
    """Обрабатывает текст для перевода."""
    from config import settings
    
    text = message.text
    
    if len(text) > settings.max_message_length:
        await message.answer(
            f"Текст слишком длинный. Максимум {settings.max_message_length} символов.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Показываем, что бот печатает
    from bot import bot
    await bot.send_chat_action(message.chat.id, "typing")
    
    data = await state.get_data()
    translation_type = data.get("translation_type")
    
    try:
        if translation_type == "slang_to_normal":
            logger.info(f"Переводим текст: {text}")
            translation, explanation = slang_service.translate_slang_to_normal(text)
            logger.info(f"Результат перевода: {translation}")
            result_text = f"Перевод со сленга:\n\n{translation}\n\nОбъяснение:\n{explanation}"
        else:
            # Для перевода на сленг показываем сообщение о том, что функция в разработке
            translation = "Не переведено"
            explanation = "Функция в разработке"
            result_text = "Перевод на сленг:\n\nК сожалению, перевод с обычного языка на сленг пока не реализован.\n\nПопробуйте перевести со сленга на обычный язык!"
        
        # Сохраняем в историю
        user_id = message.from_user.id
        if user_id not in translation_history:
            translation_history[user_id] = []
        
        translation_history[user_id].append({
            "original": text,
            "translation": translation,
            "type": translation_type,
            "explanation": explanation
        })
        
        # Ограничиваем историю
        if len(translation_history[user_id]) > settings.history_limit:
            translation_history[user_id] = translation_history[user_id][-settings.history_limit:]
        
        await message.answer(
            result_text,
            reply_markup=get_share_keyboard(result_text)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при переводе: {e}")
        await message.answer(
            "Произошла ошибка при переводе. Попробуйте еще раз.",
            reply_markup=get_cancel_keyboard()
        )
    
    await state.clear()


async def show_history(callback: CallbackQuery):
    """Показывает историю переводов."""
    user_id = callback.from_user.id
    
    if user_id not in translation_history or not translation_history[user_id]:
        await callback.message.edit_text(
            "История переводов пуста.\n\nСделай свой первый перевод!",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    history_text = "История переводов:\n\n"
    for i, item in enumerate(translation_history[user_id][-10:], 1):
        type_emoji = "Сленг" if item["type"] == "slang_to_normal" else "Обычный"
        history_text += f"{i}. {type_emoji}: {item['original'][:30]}...\n"
    
    await callback.message.edit_text(
        history_text,
        reply_markup=get_history_keyboard(translation_history[user_id])
    )


async def show_history_item(callback: CallbackQuery):
    """Показывает конкретный элемент истории."""
    try:
        item_index = int(callback.data.split("_")[-1])
        user_id = callback.from_user.id
        
        if user_id in translation_history and 0 <= item_index < len(translation_history[user_id]):
            item = translation_history[user_id][item_index]
            
            if item["type"] == "slang_to_normal":
                result_text = f"Перевод со сленга:\n\n{item['translation']}\n\nОбъяснение:\n{item['explanation']}"
            else:
                result_text = f"Перевод на сленг:\n\n{item['translation']}\n\nОбъяснение:\n{item['explanation']}"
            
            await callback.message.edit_text(
                result_text,
                reply_markup=get_share_keyboard(result_text)
            )
        else:
            await callback.answer("Элемент истории не найден.")
    except (ValueError, IndexError):
        await callback.answer("Ошибка при загрузке элемента истории.")


async def random_slang(callback: CallbackQuery):
    """Показывает случайное сленговое слово."""
    from bot import bot
    await bot.send_chat_action(callback.message.chat.id, "typing")
    
    try:
        random_word = slang_service.get_random_slang()
        if random_word:
            await callback.message.edit_text(
                f"Случайное сленговое слово:\n\n"
                f"{random_word['slang']} → {random_word['normal']}\n\n"
                f"Объяснение:\n{random_word['explanation']}",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await callback.message.edit_text(
                "Словарь пуст. Добавьте слова в JSON файл.",
                reply_markup=get_main_menu_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка при получении случайного слова: {e}")
        await callback.message.edit_text(
            "Не удалось получить случайное слово. Попробуйте позже.",
            reply_markup=get_main_menu_keyboard()
        )


async def start_search(callback: CallbackQuery, state: FSMContext):
    """Начинает поиск по словарю."""
    await callback.message.edit_text(
        "Введи значение или слово для поиска в словаре сленга:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(TranslationStates.waiting_for_search)


async def process_search(message: Message, state: FSMContext):
    """Обрабатывает поисковый запрос."""
    query = message.text
    
    from bot import bot
    await bot.send_chat_action(message.chat.id, "typing")
    
    try:
        results = slang_service.search_slang(query)
        
        if not results:
            await message.answer(
                "По вашему запросу ничего не найдено.\n\nПопробуйте другие слова или фразы.",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            search_text = f"Результаты поиска по запросу: \"{query}\"\n\n"
            
            for i, result in enumerate(results[:5], 1):
                search_text += f"{i}. {result['slang']} → {result['normal']}\n"
                search_text += f"   {result['explanation']}\n\n"
            
            await message.answer(
                search_text,
                reply_markup=get_main_menu_keyboard()
            )
    
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        await message.answer(
            "Произошла ошибка при поиске. Попробуйте еще раз.",
            reply_markup=get_main_menu_keyboard()
        )
    
    await state.clear()


async def help_command(callback: CallbackQuery):
    """Показывает справку."""
    help_text = """
Справка по использованию бота

Перевод текста
• Переводи со сленга на обычный язык
• Получай объяснения значений слов

История поиска
• Просматривай свои предыдущие переводы
• Быстро находи нужные переводы

Случайное слово
• Узнавай случайные сленговые слова
• Расширяй свой словарный запас

Поиск по словарю
• Ищи сленговые слова по значению
• Находи подходящие слова для выражения

Советы:
• Используй актуальный сленг
• Задавай конкретные вопросы
• Изучай примеры использования

Нужна помощь?
Обращайся к администратору
"""
    
    await callback.message.edit_text(
        help_text,
        reply_markup=get_main_menu_keyboard()
    )


async def cancel_command(callback: CallbackQuery, state: FSMContext):
    """Отменяет текущую операцию."""
    await state.clear()
    await callback.message.edit_text(
        "Операция отменена.",
        reply_markup=get_main_menu_keyboard()
    )


async def cancel_message(message: Message, state: FSMContext):
    """Отменяет текущую операцию через текстовое сообщение."""
    await state.clear()
    await message.answer(
        "Операция отменена.",
        reply_markup=get_main_menu_keyboard()
    )


async def back_to_main(callback: CallbackQuery):
    """Возвращает в главное меню."""
    await callback.message.edit_text(
        "Главное меню",
        reply_markup=None
    )
    await callback.message.answer(
        "Выбери действие:",
        reply_markup=get_main_menu_keyboard()
    )


async def translate_again(callback: CallbackQuery):
    """Начинает новый перевод."""
    await callback.message.edit_text(
        "Выбери тип перевода:",
        reply_markup=get_translation_type_keyboard()
    )


async def handle_unknown_message(message: Message):
    """Обрабатывает неизвестные сообщения."""
    await message.answer(
        "Не понимаю эту команду. Используйте меню для навигации.",
        reply_markup=get_main_menu_keyboard()
    )
