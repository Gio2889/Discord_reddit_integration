from utils.RedditMonitor import main
from utils.RedditBot import RedditBot
import asyncio
import os
import discord

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
        print(f"message: {message.content}")
        print(f"client user: {client.user}")
        print(f"post channel is: {bot.post_channel}")
        print(f"{type(bot.post_channel)}{type(message.channel)}")
        if message.author == client.user or str(message.channel) != bot.post_channel:
             return
        if message.content.startswith('meow'):
            embedVar = discord.Embed(title="YOU MEOWED", 
                                     description="You have meowed"
                                     , color=0x00ff00)
            img_url = "some_jpeg_url.jpeg"
            embedVar.add_field(name ="Field1", value="some messgae", inline=False)
            embedVar.set_image(url = img_url)
            #embedVar.add_field(name="Field2", value="hi2", inline=False)
            embedVar.set_footer(text="Something for the bottom of the message")
            await message.channel.send(embed=embedVar)
        # else:
        #     await message.channel.send(f'you typed something')

    
    client.run(os.getenv('DISCORD_TOKEN')) 