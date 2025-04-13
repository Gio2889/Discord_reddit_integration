import os
from utils.RedditBot import RedditBotManager
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    bot = RedditBotManager()
    bot.run(os.getenv('DISCORD_TOKEN')) 
    

    

