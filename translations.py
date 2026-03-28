TEXTS = {
    "ru": {
        # ── start ──
        "choose_lang": "🌍 Выберите язык / Choose language:",
        "welcome": (
            "👋 Добро пожаловать в агентство!\n\n"
            "Для начала работы заполните короткую анкету. "
            "Это займёт всего пару минут."
        ),
        "start_form": "📝 Начать заполнение анкеты",

        # ── form questions ──
        "q1":  "1️⃣ 👤 <b>Имя и фамилия</b>\n\nВведите ваше полное имя:",
        "q2":  "2️⃣ 📏 <b>Рост</b>\n\nВведите ваш рост в сантиметрах:",
        "q3":  "3️⃣ ⚖️ <b>Вес</b>\n\nВведите ваш вес в килограммах:",
        "q4":  "4️⃣ 📱 <b>Модель телефона</b>\n\nКакой у вас телефон?",
        "q5":  "5️⃣ 🔗 <b>Соцсети</b>\n\nУкажите ссылки или ники ваших аккаунтов (Instagram, TikTok, и т.д.):",
        "q6":  "6️⃣ 📍 <b>Место проживания</b>\n\nГород и страна:",
        "q7":  "7️⃣ 🚫 <b>Мои табу</b>\n\nЧто вы <b>не</b> готовы делать в работе?",
        "q8":  "8️⃣ 💰 <b>Желаемый уровень заработка</b>\n\nСколько вы хотите зарабатывать в месяц?",
        "q9":  "9️⃣ 💼 <b>Опыт работы</b>\n\nОпишите ваш опыт работы (или напишите «нет опыта»):",
        "q10": "🔟 🎯 <b>Цели</b>\n\nЧто вы хотите получить от работы с агентством?",

        "btn_back": "⬅️ Назад",
        "btn_cancel": "❌ Отмена",

        "form_done": (
            "✅ Анкета отправлена!\n\n"
            "Мы рассмотрим её в ближайшее время и свяжемся с вами."
        ),

        # ── main menu ──
        "btn_profile":  "📋 Профиль",
        "btn_referrals": "🤝 Рефералы",
        "btn_bonus":    "🎁 Получить бонус",
        "btn_channel":  "📢 Наш канал",
        "btn_website":  "🌐 Наш сайт",
        "btn_admin":    "🔧 Админка",
        "btn_lang":     "🌍 Язык",
        "btn_write_manager": "💬 Написать менеджеру",

        "bonus_message": (
            "🎁 <b>Ваш бонус!</b>\n\n"
            "Свяжитесь с нашим менеджером для получения персонального бонуса:\n\n"
            "👤 <b>Менеджер:</b> @agansyown\n\n"
            "Напишите менеджеру — он поможет вам начать работу!"
        ),

        # ── profile ──
        "profile_title": "📋 <b>Ваш профиль</b>\n\n",
        "profile_status": "📌 Статус: <b>{status}</b>",
        "statuses": {
            "new": "Новый",
            "filling": "Заполняет анкету",
            "reviewing": "На рассмотрении",
            "approved": "Одобрена",
            "rejected": "Отклонена",
            "active": "Активная модель",
        },
        "field_names": {
            "full_name": "👤 Имя и фамилия",
            "height": "📏 Рост",
            "weight": "⚖️ Вес",
            "phone_model": "📱 Модель телефона",
            "socials": "🔗 Соцсети",
            "location": "📍 Место проживания",
            "limits": "🚫 Табу",
            "desired_income": "💰 Желаемый доход",
            "experience": "💼 Опыт работы",
            "goals": "🎯 Цели",
            "photo_file_id": "📷 Фото профиля",
        },
        "edit_prompts": {
            "full_name": "👤 Введите ваше имя и фамилию:",
            "height": "📏 Введите ваш рост в сантиметрах:",
            "weight": "⚖️ Введите ваш вес в килограммах:",
            "phone_model": "📱 Введите модель вашего телефона:",
            "socials": "🔗 Введите ссылки или ники ваших аккаунтов (Instagram, TikTok и т.д.):",
            "location": "📍 Введите ваш город и страну:",
            "limits": "🚫 Что вы не готовы делать в работе?",
            "desired_income": "💰 Какой уровень заработка вы хотите в месяц?",
            "experience": "💼 Опишите ваш опыт работы (или напишите «нет опыта»):",
            "goals": "🎯 Что вы хотите получить от работы с агентством?",
            "photo_file_id": "📷 Отправьте фото для профиля:",
        },
        "edit_field": "✏️ Введите новое значение для поля <b>{field}</b>:",
        "field_updated": "✅ Поле обновлено!",
        "edit_cancelled": "❌ Редактирование отменено.",

        # ── referrals ──
        "referrals_title": "🤝 <b>Реферальная программа</b>\n\n",
        "ref_link": "🔗 Ваша реферальная ссылка:\n<code>{link}</code>\n\n",
        "ref_count": "👥 Приглашено: <b>{count}</b> чел.\n",
        "ref_balance": "💰 Баланс: <b>{balance:.2f} ₽</b>\n\n",
        "ref_bonuses_title": "📈 Последние начисления:\n",
        "ref_bonus_item": "• +{amount:.2f} ₽\n",
        "ref_no_bonuses": "Начислений пока нет.",
        "ref_program_info": (
            "\n\nℹ️ <b>Условия программы:</b>\n"
            "Вы получаете <b>5%</b> от дохода каждой приглашённой модели."
        ),

        # ── notifications ──
        "notify_approved": (
            "✅ <b>Ваша анкета одобрена!</b>\n\n"
            "Менеджер свяжется с вами в ближайшее время для обсуждения деталей сотрудничества."
        ),
        "notify_rejected": (
            "❌ <b>Анкета не прошла отбор</b>\n\n"
            "К сожалению, в данный момент мы не можем начать с вами сотрудничество. "
            "Вы можете обновить анкету и подать заявку повторно."
        ),
        "notify_active": (
            "🟢 <b>Поздравляем!</b>\n\n"
            "Вы стали активной моделью агентства! "
            "Добро пожаловать в команду 🎉"
        ),

        # ── admin ──
        "admin_menu": "🔧 <b>Админ-панель</b>\nВыберите раздел:",
        "admin_stats": (
            "📊 <b>Статистика</b>\n\n"
            "👥 Всего: <b>{total}</b>\n"
            "🆕 Новых: <b>{new}</b>\n"
            "📝 Заполняют: <b>{filling}</b>\n"
            "🔍 На рассмотрении: <b>{reviewing}</b>\n"
            "✅ Одобрено: <b>{approved}</b>\n"
            "🟢 Активных: <b>{active}</b>\n"
            "❌ Отклонено: <b>{rejected}</b>"
        ),
        "admin_no_models": "Список пуст.",
        "admin_model_card": (
            "👤 <b>{name}</b>\n"
            "🆔 ID: <code>{tg_id}</code>\n"
            "📱 @{username}\n"
            "📌 Статус: <b>{status}</b>\n"
            "👥 Рефералов: <b>{refs}</b>\n"
            "💰 Доход: <b>{income:.2f} ₽</b>\n\n"
            "<b>Анкета:</b>\n"
            "• Имя: {full_name}\n"
            "• Рост: {height}\n"
            "• Вес: {weight}\n"
            "• Телефон: {phone_model}\n"
            "• Соцсети: {socials}\n"
            "• Город: {location}\n"
            "• Ограничения: {limits}\n"
            "• Доход: {desired_income}\n"
            "• Опыт: {experience}\n"
            "• Цели: {goals}"
        ),
        "admin_new_anketa": (
            "🔔 <b>Новая анкета!</b>\n\n"
            "👤 {name}\n"
            "🆔 <code>{tg_id}</code>\n"
            "@{username}\n\n"
            "📋 Используйте /admin для просмотра."
        ),
        "page": "Стр. {page}/{total}",
        "btn_approve": "✅ Одобрить",
        "btn_reject": "❌ Отклонить",
        "btn_activate": "🟢 Активировать",
        "btn_back_list": "◀️ К списку",
        "btn_back_admin": "🏠 Главная админки",
        "btn_prev": "⬅️",
        "btn_next": "➡️",

        # ── new v2 keys ──
        "write_manager": "💬 Написать менеджеру",
        "manager_link": "👤 Напишите нашему менеджеру:\n@{username}",
        "broadcast_prompt": "📢 Введите сообщение для рассылки всем активным моделям:",
        "broadcast_done": "✅ Рассылка отправлена {count} моделям.",
        "weekly_summary": (
            "📊 <b>Итоги недели</b>\n\n"
            "💰 Заработок за прошлую неделю: <b>${week_total:.0f}</b>\n"
            "📅 Месяц ({month_name}): <b>${month_total:.0f}</b>\n\n"
            "Продолжайте в том же духе! 💪"
        ),
        "monthly_summary": (
            "📊 <b>Итоги месяца</b>\n\n"
            "💰 Итого за {month_name}: <b>${month_total:.0f}</b>\n"
            "🎁 Реф. бонусы: <b>{ref_total:.2f} ₽</b>\n\n"
            "Спасибо за работу! Новый месяц — новые возможности 🚀"
        ),
        "admin_reminder": "⏰ <b>Напоминание!</b>\nЕсть {count} заявок на рассмотрении дольше 24 часов.",
        "note_added": "✅ Заметка добавлена!",
        "notes_empty": "Заметок нет.",
        "status_history_title": "📋 История статусов:",
        "photo_saved": "✅ Фото сохранено!",
        "photo_prompt": "📷 Отправьте фото для профиля:",
    },

    "en": {
        "choose_lang": "🌍 Выберите язык / Choose language:",
        "welcome": (
            "👋 Welcome to the agency!\n\n"
            "Please fill out a short application form. "
            "It will only take a couple of minutes."
        ),
        "start_form": "📝 Start the application",

        "q1":  "1️⃣ 👤 <b>Full name</b>\n\nEnter your full name:",
        "q2":  "2️⃣ 📏 <b>Height</b>\n\nEnter your height in centimeters:",
        "q3":  "3️⃣ ⚖️ <b>Weight</b>\n\nEnter your weight in kilograms:",
        "q4":  "4️⃣ 📱 <b>Phone model</b>\n\nWhat phone do you use?",
        "q5":  "5️⃣ 🔗 <b>Social media</b>\n\nProvide links or usernames (Instagram, TikTok, etc.):",
        "q6":  "6️⃣ 📍 <b>Location</b>\n\nCity and country:",
        "q7":  "7️⃣ 🚫 <b>My taboos</b>\n\nWhat are you <b>NOT</b> willing to do at work?",
        "q8":  "8️⃣ 💰 <b>Desired income</b>\n\nHow much do you want to earn per month?",
        "q9":  "9️⃣ 💼 <b>Work experience</b>\n\nDescribe your experience (or write «no experience»):",
        "q10": "🔟 🎯 <b>Goals</b>\n\nWhat do you want to get from working with the agency?",

        "btn_back": "⬅️ Back",
        "btn_cancel": "❌ Cancel",

        "form_done": (
            "✅ Application submitted!\n\n"
            "We will review it shortly and get back to you."
        ),

        "btn_profile":  "📋 Profile",
        "btn_referrals": "🤝 Referrals",
        "btn_bonus":    "🎁 Get bonus",
        "btn_channel":  "📢 Our channel",
        "btn_website":  "🌐 Our website",
        "btn_admin":    "🔧 Admin panel",
        "btn_lang":     "🌍 Language",
        "btn_write_manager": "💬 Write to manager",

        "bonus_message": (
            "🎁 <b>Your bonus!</b>\n\n"
            "Contact our manager to get your personal bonus:\n\n"
            "👤 <b>Manager:</b> @agansyown\n\n"
            "Write to the manager — they'll help you get started!"
        ),

        "profile_title": "📋 <b>Your profile</b>\n\n",
        "profile_status": "📌 Status: <b>{status}</b>",
        "statuses": {
            "new": "New",
            "filling": "Filling form",
            "reviewing": "Under review",
            "approved": "Approved",
            "rejected": "Rejected",
            "active": "Active model",
        },
        "field_names": {
            "full_name": "👤 Full name",
            "height": "📏 Height",
            "weight": "⚖️ Weight",
            "phone_model": "📱 Phone model",
            "socials": "🔗 Social media",
            "location": "📍 Location",
            "limits": "🚫 Taboos",
            "desired_income": "💰 Desired income",
            "experience": "💼 Work experience",
            "goals": "🎯 Goals",
            "photo_file_id": "📷 Profile photo",
        },
        "edit_prompts": {
            "full_name": "👤 Enter your full name:",
            "height": "📏 Enter your height in centimeters:",
            "weight": "⚖️ Enter your weight in kilograms:",
            "phone_model": "📱 Enter your phone model:",
            "socials": "🔗 Enter your social media links or usernames (Instagram, TikTok, etc.):",
            "location": "📍 Enter your city and country:",
            "limits": "🚫 What are you NOT willing to do at work?",
            "desired_income": "💰 How much do you want to earn per month?",
            "experience": "💼 Describe your work experience (or write «no experience»):",
            "goals": "🎯 What do you want to get from working with the agency?",
            "photo_file_id": "📷 Send a photo for your profile:",
        },
        "edit_field": "✏️ Enter new value for <b>{field}</b>:",
        "field_updated": "✅ Field updated!",
        "edit_cancelled": "❌ Editing cancelled.",

        "referrals_title": "🤝 <b>Referral program</b>\n\n",
        "ref_link": "🔗 Your referral link:\n<code>{link}</code>\n\n",
        "ref_count": "👥 Invited: <b>{count}</b> people\n",
        "ref_balance": "💰 Balance: <b>{balance:.2f} ₽</b>\n\n",
        "ref_bonuses_title": "📈 Recent bonuses:\n",
        "ref_bonus_item": "• +{amount:.2f} ₽\n",
        "ref_no_bonuses": "No bonuses yet.",
        "ref_program_info": (
            "\n\nℹ️ <b>Program terms:</b>\n"
            "You receive <b>5%</b> of income from each invited model."
        ),

        "notify_approved": (
            "✅ <b>Your application is approved!</b>\n\n"
            "A manager will contact you shortly to discuss cooperation details."
        ),
        "notify_rejected": (
            "❌ <b>Application not approved</b>\n\n"
            "Unfortunately, we cannot start cooperation at this time. "
            "You may update your form and apply again."
        ),
        "notify_active": (
            "🟢 <b>Congratulations!</b>\n\n"
            "You are now an active model of the agency! "
            "Welcome to the team 🎉"
        ),

        "admin_menu": "🔧 <b>Admin panel</b>\nChoose section:",
        "admin_stats": (
            "📊 <b>Statistics</b>\n\n"
            "👥 Total: <b>{total}</b>\n"
            "🆕 New: <b>{new}</b>\n"
            "📝 Filling: <b>{filling}</b>\n"
            "🔍 Reviewing: <b>{reviewing}</b>\n"
            "✅ Approved: <b>{approved}</b>\n"
            "🟢 Active: <b>{active}</b>\n"
            "❌ Rejected: <b>{rejected}</b>"
        ),
        "admin_no_models": "List is empty.",
        "admin_model_card": (
            "👤 <b>{name}</b>\n"
            "🆔 ID: <code>{tg_id}</code>\n"
            "📱 @{username}\n"
            "📌 Status: <b>{status}</b>\n"
            "👥 Referrals: <b>{refs}</b>\n"
            "💰 Income: <b>{income:.2f} ₽</b>\n\n"
            "<b>Application:</b>\n"
            "• Name: {full_name}\n"
            "• Height: {height}\n"
            "• Weight: {weight}\n"
            "• Phone: {phone_model}\n"
            "• Socials: {socials}\n"
            "• Location: {location}\n"
            "• Limits: {limits}\n"
            "• Income goal: {desired_income}\n"
            "• Experience: {experience}\n"
            "• Goals: {goals}"
        ),
        "admin_new_anketa": (
            "🔔 <b>New application!</b>\n\n"
            "👤 {name}\n"
            "🆔 <code>{tg_id}</code>\n"
            "@{username}\n\n"
            "📋 Use /admin to view."
        ),
        "page": "Page {page}/{total}",
        "btn_approve": "✅ Approve",
        "btn_reject": "❌ Reject",
        "btn_activate": "🟢 Activate",
        "btn_back_list": "◀️ Back to list",
        "btn_back_admin": "🏠 Admin home",
        "btn_prev": "⬅️",
        "btn_next": "➡️",

        # ── new v2 keys ──
        "write_manager": "💬 Write to manager",
        "manager_link": "👤 Write to our manager:\n@{username}",
        "broadcast_prompt": "📢 Enter the message to broadcast to all active models:",
        "broadcast_done": "✅ Broadcast sent to {count} models.",
        "weekly_summary": (
            "📊 <b>Weekly summary</b>\n\n"
            "💰 Earnings last week: <b>${week_total:.0f}</b>\n"
            "📅 Month ({month_name}): <b>${month_total:.0f}</b>\n\n"
            "Keep it up! 💪"
        ),
        "monthly_summary": (
            "📊 <b>Monthly summary</b>\n\n"
            "💰 Total for {month_name}: <b>${month_total:.0f}</b>\n"
            "🎁 Referral bonuses: <b>{ref_total:.2f} ₽</b>\n\n"
            "Thank you for your work! New month, new opportunities 🚀"
        ),
        "admin_reminder": "⏰ <b>Reminder!</b>\nThere are {count} applications under review for more than 24 hours.",
        "note_added": "✅ Note added!",
        "notes_empty": "No notes.",
        "status_history_title": "📋 Status history:",
        "photo_saved": "✅ Photo saved!",
        "photo_prompt": "📷 Send a photo for your profile:",
    }
}


def t(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in TEXTS else "ru"
    text = TEXTS[lang].get(key, TEXTS["ru"].get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def ts(lang: str, key: str) -> str:
    """Get sub-dict (e.g. statuses, field_names)."""
    lang = lang if lang in TEXTS else "ru"
    return TEXTS[lang].get(key, TEXTS["ru"].get(key, {}))
