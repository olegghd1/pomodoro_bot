from datetime import datetime, timedelta, date
import aiosqlite

path_to_db = r"tgbot/db/main.db"


async def create_table():
    async with aiosqlite.connect(path_to_db) as db:
        await db.execute(f"""CREATE TABLE IF NOT EXISTS users(
                         id INTEGER PRIMARY KEY,
                         telegram_id INTEGER,
                         work_time INTEGER DEFAULT 25,
                         rest_time INTEGER DEFAULT 5,
                         sprint_time INTEGER DEFAULT 4,
                         sprint_or_timer INTEGER DEFAULT 2,
                         pomodoro_or_rest INTEGER,
                         pomodoro_step INTEGER DEFAULT 0,
                         end_date TEXT,
                         all_pomodoro INTEGER DEFAULT 0,
                         all_pomodoro_time INTEGER DEFAULT 0,
                         today_pomodoro INTEGER DEFAULT 0,
                         today_pomodoro_time INTEGER DEFAULT 0,
                         today_stats TEXT,
                         registration_date TEXT
                         )""")
        await db.commit()


async def add_or_return_user(user_id):
    async with aiosqlite.connect(path_to_db) as db:
        parameters = (user_id,)
        sql = "SELECT * FROM users WHERE telegram_id=?"
        cursor = await db.execute(sql, parameters)
        user = await cursor.fetchone()
        if user:
            return user
        else:
            sql = "INSERT INTO users (telegram_id, today_stats, registration_date) VALUES(?, ?, ?)"
            today = date.today().isoformat()
            parameters = (user_id, today, today)
            await db.execute(sql, parameters)
            await db.commit()
            parameters = (user_id,)
            sql = "SELECT * FROM users WHERE telegram_id=?"
            cursor = await db.execute(sql, parameters)
            user = await cursor.fetchone()
            return user


async def change_sprint_or_timer_on_finish():
    async with aiosqlite.connect(path_to_db) as db:
        sql = "UPDATE users SET pomodoro_step=0, sprint_or_timer=2"
        await db.execute(sql)
        await db.commit()


async def change_sprint_or_timer(user_id, state):
    async with aiosqlite.connect(path_to_db) as db:
        parameters = (state, user_id,)
        sql = "UPDATE users SET pomodoro_step=0, sprint_or_timer=? WHERE telegram_id=?"
        await db.execute(sql, parameters)
        await db.commit()


async def update_table_with_timer_started(user_id, work_time):
    end_date = (datetime.now() + timedelta(minutes=work_time)).isoformat()
    async with aiosqlite.connect(path_to_db) as db:
        parameters = (end_date, user_id)
        sql = "UPDATE users SET end_date=? WHERE telegram_id=?"
        await db.execute(sql, parameters)
        await db.commit()


async def update_table_with_pomo_started(user_id, work_time):
    end_date = (datetime.now() + timedelta(minutes=work_time)).isoformat()
    async with aiosqlite.connect(path_to_db) as db:
        parameters = (user_id,)
        sql = "SELECT pomodoro_step FROM users WHERE telegram_id=?"
        cursor = await db.execute(sql, parameters)
        step = await cursor.fetchone()
        step = step[0] + 1
        parameters = (step, 0, end_date, user_id)
        sql = "UPDATE users SET pomodoro_step=?, pomodoro_or_rest=?, end_date=? WHERE telegram_id=?"
        await db.execute(sql, parameters)
        await db.commit()


async def update_today_stats(db):
    sql = "SELECT today_stats FROM users"
    cursor = await db.execute(sql)
    tuple_ = await cursor.fetchone()
    stats_date = date.fromisoformat(tuple_[0])
    today = date.today()
    if stats_date < today:
        sql = "UPDATE users SET today_stats=?, today_pomodoro, today_pomodoro_time"
        now = today.isoformat()
        params = (now, 0, 0)
        await db.execute(sql, params)
        await db.commit()
    return


async def update_table_with_rest_started(user_id, rest_time):
    end_date = (datetime.now() + timedelta(minutes=rest_time)).isoformat()
    async with aiosqlite.connect(path_to_db) as db:
        await update_today_stats(db)
        parameters = (user_id,)
        sql = """SELECT work_time, all_pomodoro, all_pomodoro_time, today_pomodoro, 
        today_pomodoro_time FROM users WHERE telegram_id=?"""
        cursor = await db.execute(sql, parameters)
        tuple_ = await cursor.fetchone()
        work_time, all_pomodoro, all_pomodoro_time, today_pomodoro, today_pomodoro_time = tuple_
        all_pomodoro_time += work_time
        today_pomodoro_time += work_time
        all_pomodoro += 1
        today_pomodoro += 1
        parameters = (all_pomodoro, all_pomodoro_time, today_pomodoro, today_pomodoro_time, 1, end_date, user_id)
        sql = """UPDATE users SET all_pomodoro=?, all_pomodoro_time=?, today_pomodoro=?, 
        today_pomodoro_time=?, pomodoro_or_rest=?, end_date=? WHERE telegram_id=?"""
        await db.execute(sql, parameters)
        await db.commit()


async def update_table_with_sprint_finished(user_id):
    async with aiosqlite.connect(path_to_db) as db:
        await update_today_stats(db)
        parameters = (user_id,)
        sql = """SELECT work_time, all_pomodoro, all_pomodoro_time, today_pomodoro, 
        today_pomodoro_time FROM users WHERE telegram_id=?"""
        cursor = await db.execute(sql, parameters)
        tuple_ = await cursor.fetchone()
        work_time, all_pomodoro, all_pomodoro_time, today_pomodoro, today_pomodoro_time = tuple_
        all_pomodoro_time += work_time
        today_pomodoro_time += work_time
        all_pomodoro += 1
        today_pomodoro += 1
        parameters = (all_pomodoro, all_pomodoro_time, today_pomodoro, today_pomodoro_time, 3, 0, user_id)
        sql = """UPDATE users SET all_pomodoro=?, all_pomodoro_time=?, today_pomodoro=?, 
        today_pomodoro_time=?, sprint_or_timer=?, pomodoro_step=? WHERE telegram_id=?"""
        await db.execute(sql, parameters)
        await db.commit()


async def update_table_with_timer_finished(user_id, work_time):
    async with aiosqlite.connect(path_to_db) as db:
        await update_today_stats(db)
        parameters = (user_id,)
        sql = """SELECT all_pomodoro, all_pomodoro_time, today_pomodoro, 
        today_pomodoro_time FROM users WHERE telegram_id=?"""
        cursor = await db.execute(sql, parameters)
        tuple_ = await cursor.fetchone()
        all_pomodoro, all_pomodoro_time, today_pomodoro, today_pomodoro_time = tuple_
        all_pomodoro_time += work_time
        today_pomodoro_time += work_time
        all_pomodoro += 1
        today_pomodoro += 1
        parameters = (all_pomodoro, all_pomodoro_time, today_pomodoro, today_pomodoro_time, 3, user_id)
        sql = """UPDATE users SET all_pomodoro=?, all_pomodoro_time=?, today_pomodoro=?, 
        today_pomodoro_time=?, sprint_or_timer=? WHERE telegram_id=?"""
        await db.execute(sql, parameters)
        await db.commit()


async def update_work_time(user_id, time):
    async with aiosqlite.connect(path_to_db) as db:
        sql = 'SELECT rest_time, sprint_time FROM users WHERE telegram_id=?'
        parameters = (user_id, )
        cursor = await db.execute(sql, parameters)
        tuple_ = await cursor.fetchone()
        sql = 'UPDATE users SET work_time=? WHERE telegram_id=?'
        parameters = (time, user_id)
        await db.execute(sql, parameters)
        await db.commit()
        return tuple_


async def update_rest_time(user_id, time):
    async with aiosqlite.connect(path_to_db) as db:
        sql = 'SELECT work_time, sprint_time FROM users WHERE telegram_id=?'
        parameters = (user_id, )
        cursor = await db.execute(sql, parameters)
        tuple_ = await cursor.fetchone()
        sql = 'UPDATE users SET rest_time=? WHERE telegram_id=?'
        parameters = (time, user_id)
        await db.execute(sql, parameters)
        await db.commit()
        return tuple_


async def update_sprint_time(user_id, time):
    async with aiosqlite.connect(path_to_db) as db:
        sql = 'SELECT work_time, rest_time FROM users WHERE telegram_id=?'
        parameters = (user_id, )
        cursor = await db.execute(sql, parameters)
        tuple_ = await cursor.fetchone()
        sql = 'UPDATE users SET sprint_time=? WHERE telegram_id=?'
        parameters = (time, user_id)
        await db.execute(sql, parameters)
        await db.commit()
        return tuple_