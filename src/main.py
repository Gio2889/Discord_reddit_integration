from utils.RedditMonitor import main
from utils.RedditBot import RedditBot
import asyncio
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
if __name__ == '__main__':
    # test for reddit call
    #asyncio.run(main())
    #######
    bot = RedditBot()
    client = bot.client
    

    @client.event
    async def on_ready():
        print(f'We have logged in as {client.user}')

    @client.event
    async def on_message(message):
        print("message detected")
        print(f"author: {message.author}")
        print(f"channel: {message.channel}")
        print(f"message: {message}")
        print(f"message: {message.content}")
        # if message.author == client.user:
        #     return
        #if message.content.startswith('$hello'):
        if message.content:
            await message.channel.reply(f'you typed:\n {message.content}')
    client.run(os.getenv('DISCORD_TOKEN')) 