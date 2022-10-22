from environs import Env

env = Env()
env.read_env()
token = env.str("BOT_TOKEN")