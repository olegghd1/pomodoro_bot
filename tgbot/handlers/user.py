from datetime import datetime, timedelta, date
from aiogram import Dispatcher, types, filters
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tgbot.db.aiosqlite_db import add_or_return_user, change_sprint_or_timer, update_table_with_pomo_started, \
    update_table_with_rest_started, update_table_with_sprint_finished, update_table_with_timer_finished, \
    update_work_time, update_rest_time, update_sprint_time, update_table_with_timer_started, update_today_stats


# Form the keyboard depending on whether the sprint is running or not
def user_start_keyboard(sprint_or_timer):
    if sprint_or_timer == 0:
        text = '/stop_sprint'
    else:
        text = '/start_sprint'
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=text), KeyboardButton(text='/help')],
            [KeyboardButton(text='/stats'), KeyboardButton(text='/cancel')]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard


# /start command The first time we add the user to the database but if he is already in the database
# we check whether the sprint is runnung or not
async def start_bot(message: types.Message):
    user_id = message.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    await message.answer(text=(
        "Hi, I'm your Pomodoro Timer. Let's work? Send me minutes to set the timer "
        "to. Send /rules to see Pomodoro Technique. Send "
        "/settings to change sprint details, like pomodoro, rest duration, long rest "
        "duration and sprint duration.\n\n"
    ), reply_markup=user_start_keyboard(sprint_or_timer))


# /start_sprint
async def start_sprint(message: types.Message, scheduler: AsyncIOScheduler):
    user_id = message.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    # check if sprint or timer has already started
    if sprint_or_timer == 0:
        scheduler.remove_job(f'{user_id}_pomo')
        scheduler.remove_job(f'{user_id}_rest')
        scheduler.remove_job(f'{user_id}_finish')
    elif sprint_or_timer == 1:
        scheduler.remove_job(f'{user_id}_timer')
        await change_sprint_or_timer(user_id, 0)
    else:
        await change_sprint_or_timer(user_id, 0)
    sprint_time = user[4]
    rest_time = user[3]
    work_time = user[2]
    sprint_time = (work_time + rest_time) * sprint_time - rest_time
    # schedule messages about pomodoro started, rest started, pomodoro finished
    schedule_sprint(message, scheduler, user)
    # update info about current pomodoro for inline_button with hourglass
    await update_table_with_pomo_started(user_id, work_time)
    await message.answer(text=(
        "Sprint started. It will last {sprint_time} "
        "minutes or until you stop it. Pomodoro {work_time} minutes started."
    ).format(sprint_time=sprint_time, work_time=work_time), reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='⏳', callback_data='time')]
        ]
    ))


def schedule_sprint(message: types.Message, scheduler: AsyncIOScheduler, user):
    user_id = user[1]
    sprint_time = user[4]
    rest_time = user[3]
    work_time = user[2]
    end = (work_time + rest_time) * (sprint_time - 1)
    interval = rest_time + work_time
    now = datetime.now()
    scheduler.add_job(send_about_pomo_started, 'interval', start_date=now + timedelta(minutes=interval),
                      minutes=interval,
                      end_date=now + timedelta(minutes=end), id=f'{user_id}_pomo', args=(message, work_time,))
    start = work_time
    end = (work_time + rest_time) * (sprint_time - 1) - rest_time
    scheduler.add_job(send_about_rest_started, 'interval', start_date=now + timedelta(minutes=start), minutes=interval,
                      end_date=now + timedelta(minutes=end), id=f'{user_id}_rest', args=(message, rest_time,))
    run_date = (work_time + rest_time) * sprint_time - rest_time
    scheduler.add_job(send_about_sprint_finished, 'date', run_date=now + timedelta(minutes=run_date),
                      id=f'{user_id}_finish', args=(message,))


async def send_about_pomo_started(message: types.Message, work_time):
    user_id = message.from_user.id
    await update_table_with_pomo_started(user_id, work_time)
    await message.answer(text=f"Pomodoro {work_time} minutes started.", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='⏳', callback_data='time')]
        ]
    ))


async def send_about_rest_started(message: types.Message, rest_time):
    user_id = message.from_user.id
    await update_table_with_rest_started(user_id, rest_time)
    await message.answer(text=f"Pomodoro is done, please have {rest_time} minutes rest now.")


async def send_about_sprint_finished(message: types.Message):
    user_id = message.from_user.id
    await update_table_with_sprint_finished(user_id)
    await message.answer(text="Congratulations, your sprint is done! How do you feel?",
                         reply_markup=user_start_keyboard(2))


# inline button with hourglass
async def show_left_time(callback: types.CallbackQuery):
    user = await add_or_return_user(callback.from_user.id)
    end_date = user[8]
    sprint_or_timer = user[5]
    if sprint_or_timer == 0:
        sprint_duration = user[4]
        pomodoro_or_rest = user[6]
        pomodoro_step = user[7]
        text = format_current_pomodoro(sprint_duration, pomodoro_or_rest, pomodoro_step, end_date)
    elif sprint_or_timer == 1:
        text = format_timer(end_date)
    else:
        text = "No running pomodoros"
    await callback.answer(text)


def format_current_pomodoro(sprint_duration, pomodoro_or_rest, pomodoro_step, end_date):
    now = datetime.now()
    end_date = datetime.fromisoformat(end_date)
    seconds = (end_date - now).total_seconds()
    seconds = int(seconds)
    if pomodoro_or_rest == 0:
        if seconds < 60:
            text = "{time} seconds left, pomodoro #{current_pomodoro} of {all_pomodoro}."
            time = seconds
        else:
            time = seconds // 60
            if time == 1:
                text = "about {time} minute left, pomodoro #{current_pomodoro} of {all_pomodoro}."
            else:
                text = "about {time} minutes left, pomodoro #{current_pomodoro} of {all_pomodoro}."
        text = text.format(time=time, current_pomodoro=pomodoro_step, all_pomodoro=sprint_duration)
    else:
        if seconds < 60:
            text = "Rest time, {time} seconds left"
            time = seconds
        else:
            time = seconds // 60
            if time == 1:
                text = "Rest time, about {time} minute left"
            else:
                text = "Rest time, about {time} minutes left"
        text = text.format(time=time)
    return text


def format_timer(end_date):
    end_date = datetime.fromisoformat(end_date)
    seconds = (end_date - datetime.now()).total_seconds()
    seconds = int(seconds)
    if seconds < 60:
        text = '{time} seconds left.'
        text = text.format(time=seconds)
    else:
        minutes = seconds // 60
        if minutes == 1:
            text = 'about {time} minute left.'
        else:
            text = 'about {time} minutes left.'
        text = text.format(time=minutes)
    return text


# /stop_sprint
async def stop_sprint(message: types.Message, scheduler: AsyncIOScheduler):
    user_id = message.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    if sprint_or_timer != 0:
        await message.answer(text=("Sorry, I cannot find an ongoing sprint. Send /start_sprint to start one."),
                             reply_markup=user_start_keyboard(2))
    else:
        scheduler.remove_job(f'{user_id}_pomo')
        scheduler.remove_job(f'{user_id}_rest')
        scheduler.remove_job(f'{user_id}_finish')
        await change_sprint_or_timer(user_id, 2)
        await message.answer(text=("You are done with this sprint.\n\n"
                                   "OK, no problem."), reply_markup=user_start_keyboard(2))


# send any number to bot, works like /start_sprint
async def start_timer(message: types.Message, scheduler: AsyncIOScheduler):
    print('hello')
    minutes = int(message.text)
    if minutes > 1440:
        await message.answer("Working more than one day is unhealthy, enter a number less than 1440")
        return
    user_id = message.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    if sprint_or_timer == 0:
        scheduler.remove_job(f'{user_id}_rest')
        scheduler.remove_job(f'{user_id}_pomo')
        scheduler.remove_job(f'{user_id}_finish')
        await change_sprint_or_timer(user_id, 1)
    elif sprint_or_timer == 1:
        scheduler.remove_job(f'{user_id}_timer')
    else:
        await change_sprint_or_timer(user_id, 1)
    scheduler.add_job(send_about_timer_finished, 'date', run_date=datetime.now() + timedelta(minutes=minutes),
                      id=f'{user_id}_timer', args=(message, minutes,))
    await update_table_with_timer_started(user_id, minutes)
    await message.answer(f"Pomodoro {minutes} minutes started.", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='⏳', callback_data='time')]
        ]))


async def send_about_timer_finished(message: types.Message, work_time):
    user_id = message.from_user.id
    await update_table_with_timer_finished(user_id, work_time)
    await message.answer(text="Pomodoro done! How's it going?", reply_markup=user_start_keyboard(2))


# /cancel
async def cancel(message: types.Message, scheduler: AsyncIOScheduler):
    user_id = message.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    if sprint_or_timer == 0:
        scheduler.remove_job(f'{user_id}_rest')
        scheduler.remove_job(f'{user_id}_pomo')
        scheduler.remove_job(f'{user_id}_finish')
    elif sprint_or_timer == 1:
        scheduler.remove_job(f'{user_id}_timer')
    else:
        pass
    await change_sprint_or_timer(user_id, 3)
    await message.answer("Ok, no problem.", reply_markup=user_start_keyboard(2))


# /stats
async def show_stats(message: types.Message):
    await update_today_stats()

    def format_time(time):
        time = int(time)
        if time < 60:
            return f"{time} minutes"
        elif 60 <= time < 1440:
            minutes = time % 60
            hours = time // 60
            return f"{hours} hour{'s'[:hours ^ 1]}, {minutes} minute{'s'[:minutes ^ 1]}"
        else:
            days = time // 1440
            time = time % 1440
            hours = time // 60
            minutes = time % 60
            return f"{days} day{'s'[:days ^ 1]}, {hours} hour{'s'[:hours ^ 1]}, {minutes} minute{'s'[:minutes ^ 1]}"

    user_id = message.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    all_pomodoro = user[9]
    all_pomodoro_time = user[10]
    today_pomodoro = user[11]
    today_pomodoro_time = user[12]
    registration_date = user[14]
    registration_date = date.fromisoformat(registration_date)
    last_date = date.today() - registration_date
    last_date = last_date.days
    if all_pomodoro and today_pomodoro and last_date:
        today_pomodoro_time = format_time(today_pomodoro_time)
        all_pomodoro_time = format_time(all_pomodoro_time)
        text = (f"You did {today_pomodoro} pomodoro{'s'[:today_pomodoro ^ 1]} ({today_pomodoro_time}) today. Good "
                f"job!\n\n "
                f"You also have completed {all_pomodoro} pomodoro{'s'[:all_pomodoro ^ 1]} ({all_pomodoro_time}) "
                f"in last {last_date} day{'s'[:last_date ^ 1]}, by the way.")
    elif today_pomodoro:
        today_pomodoro_time = format_time(today_pomodoro_time)
        text = f"You did {today_pomodoro} pomodoro{'s'[:today_pomodoro ^ 1]} ({today_pomodoro_time}) today. Good job!"
    else:
        text = "You have no completed pomodoros today. But don't upset!\nThere is still time to start one."
    await message.answer(text=text, reply_markup=user_start_keyboard(sprint_or_timer))


# /rules
async def show_rules(message: types.Message):
    user_id = message.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    await message.answer(text=("Pomodoro Technique consists of 5 simple steps:\n"
                               "1. Choose the task\n"
                               "2. Start the timer\n"
                               "3. Work on the task until the timer rings\n"
                               "4. Take a short break (3-5 minutes)\n"
                               "5. After four pomodoros, take a longer break (15-30 minutes).\n\n"
                               "Sprint consists of four 25-minutes pomodoros."),
                         reply_markup=user_start_keyboard(sprint_or_timer))


# /settings
async def change_settings(message: types.Message):
    # TODO sprint pomodoro duration 1 60, rest 1 60, duration 20
    await message.answer("Please choose option to change:", reply_markup=ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="change sprint pomodoro duration")],
            [KeyboardButton(text="Change sprint rest duration")],
            [KeyboardButton(text="Change sprint duration")],
            [KeyboardButton(text="Done, get me back to pomodoros")]
        ]
    ))


get_back_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Done, get me back to pomodoros',
                              callback_data='get_back')]
    ]
)


async def change_work_time(message: types.Message, state: FSMContext):
    await state.set_state('enter_work_time')
    await message.answer(text='Enter the number of minutes you want to set (from 1 to 60)',
                         reply_markup=get_back_keyboard)


async def enter_work_time(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    try:
        number = int(message.text)
    except ValueError:
        await message.answer("Error!\nEnter the number from 1 to 60")
        return
    if number > 60:
        await message.answer("Error!\nToo many minutes. Enter the number from 1 to 60.")
        return
    params = await update_work_time(message.from_user.id, number)
    rest_time, sprint_duration = params
    rest_time = int(rest_time)
    work_time = number
    await message.answer(text=(f"Done, sprint settings saved. Your sprint now consists of {sprint_duration} pomodoros"
                               f" {work_time} minute{'s'[:work_time ^ 1]} each, rest time {rest_time} "
                               f"minute{'s'[:rest_time ^ 1]}. Send /settings to change other settings."),
                         reply_markup=user_start_keyboard(sprint_or_timer))
    await state.reset_state()


async def change_rest_time(message: types.Message, state: FSMContext):
    await state.set_state('enter_rest_time')
    await message.answer(text='Enter the number of minutes you want to set (from 1 to 60)',
                         reply_markup=get_back_keyboard)


async def enter_rest_time(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    try:
        number = int(message.text)
    except ValueError:
        await message.answer("Error!\nEnter the number from 1 to 60")
        return
    if number > 60:
        await message.answer("Error!\nToo many minutes. Enter the number from 1 to 60.")
        return
    params = await update_rest_time(message.from_user.id, number)
    work_time, sprint_duration = params
    rest_time = number
    await message.answer(text=(f"Done, sprint settings saved. Your sprint now consists of {sprint_duration} pomodoros"
                               f" {work_time} minute{'s'[:work_time ^ 1]} each, rest time {rest_time} "
                               f"minute{'s'[:rest_time ^ 1]}. Send /settings to change other settings."),
                         reply_markup=user_start_keyboard(sprint_or_timer))
    await state.reset_state()


async def change_sprint_time(message: types.Message, state: FSMContext):
    await state.set_state('enter_sprint_time')
    await message.answer(text='Enter the number of pomodoro you want to set (from 2 to 20)',
                         reply_markup=get_back_keyboard)


async def enter_sprint_time(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    try:
        number = int(message.text)
    except ValueError:
        await message.answer("Error!\nEnter the number from 2 to 20")
        return
    if number > 20:
        await message.answer("Error!\nToo many pomodoros. Enter the number from 2 to 20.")
        return
    elif number < 2:
        await message.answer("Error!\nToo few pomodoros. Enter the number from 2 to 20.")
        return
    params = await update_sprint_time(message.from_user.id, number)
    work_time, rest_time = params
    sprint_duration = number
    await message.answer(text=(f"Done, sprint settings saved. Your sprint now consists of {sprint_duration} pomodoros"
                               f" {work_time} minute{'s'[:work_time ^ 1]} each, rest time {rest_time} "
                               f"minute{'s'[:rest_time ^ 1]}. Send /settings to change other settings."),
                         reply_markup=user_start_keyboard(sprint_or_timer))
    await state.reset_state()


async def back_to_pomodoros_inline_button(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    await callback.message.delete()
    await state.reset_state()
    await callback.message.answer("Ok, got it.", reply_markup=user_start_keyboard(sprint_or_timer))


async def back_to_pomodoros(message: types.Message):
    user_id = message.from_user.id
    user = await add_or_return_user(user_id)
    sprint_or_timer = user[5]
    await message.answer("Ok, got it.", reply_markup=user_start_keyboard(sprint_or_timer))


def register_user_handlers(dp: Dispatcher):
    dp.register_message_handler(start_bot, commands=['start', 'help'])
    dp.register_message_handler(start_sprint, commands=['start_sprint'])
    dp.register_callback_query_handler(show_left_time, text='time')
    dp.register_message_handler(stop_sprint, commands=["stop_sprint"])
    dp.register_message_handler(start_timer, regexp='^\d*$')
    dp.register_message_handler(cancel, commands=['cancel'])
    dp.register_message_handler(show_rules, commands=['rules'])
    dp.register_message_handler(change_settings, commands=['settings'])
    dp.register_message_handler(change_work_time, text='change sprint pomodoro duration')
    dp.register_message_handler(enter_work_time, state='enter_work_time')
    dp.register_message_handler(change_rest_time, text='Change sprint rest duration')
    dp.register_message_handler(enter_rest_time, state='enter_rest_time')
    dp.register_message_handler(change_sprint_time, text='Change sprint duration')
    dp.register_message_handler(enter_sprint_time, state='enter_sprint_time')
    dp.register_callback_query_handler(back_to_pomodoros_inline_button, state=['enter_work_time', 'enter_rest_time',
                                                                               'enter_sprint_time'])
    dp.register_message_handler(back_to_pomodoros, text='Done, get me back to pomodoros')
    dp.register_message_handler(show_stats, commands=['stats'])
