from utils.RedditMonitor import main
from utils.RedditBot import RedditBotManager
import asyncio
import os
import discord
from discord.ext import commands

os.chdir(os.path.dirname(os.path.abspath(__file__)))
if __name__ == '__main__':
    # test for reddit call
    #asyncio.run(main())
    #######
    mngr = RedditBotManager()
    #client = mngr.client
    bot = mngr.bot

    @bot.event
    async def on_ready():
        print(f'We have logged in as {bot.user}')

    # @bot.event
    # async def on_message(message):
    #     print("message detected")
    #     print(f"author: {message.author}")
    #     print(f"channel: {message.channel}")
    #     print(f"message: {message.content}")
    #     print(f"client user: {bot.user}")
    #     print(f"post channel is: {mngr.post_channel}")
    #     print(f"{type(mngr.post_channel)}{type(message.channel)}")
    #     if message.author == bot.user or str(message.channel) != mngr.post_channel:
    #          return
    #     if message.content.startswith('meow'):
    #         embedVar = discord.Embed(title="YOU MEOWED", 
    #                                  description="You have meowed"
    #                                  , color=0x00ff00)
    #         img_url = "some_jpeg_url.jpeg"
    #         embedVar.add_field(name ="Field1", value="some messgae", inline=False)
    #         embedVar.set_image(url = img_url)
    #         #embedVar.add_field(name="Field2", value="hi2", inline=False)
    #         embedVar.set_footer(text="Something for the bottom of the message")
    #         await message.channel.send(embed=embedVar)
    #     else:
    #         await message.channel.send("message observed")
        
    @bot.command()
    async def test(ctx, *args):
        print("command called")
        arguments = ', '.join(args)
        await ctx.send(f'{len(args)} arguments: {arguments}')

    @bot.command()
    async def add(ctx, left : int, right : int):
        """Adds two numbers together."""
        await ctx.send(left + right)

    

    bot.run(os.getenv('DISCORD_TOKEN')) 