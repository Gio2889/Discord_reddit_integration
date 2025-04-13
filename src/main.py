from utils.RedditMonitor import main
from utils.RedditBot import RedditBotManager
import asyncio
import os
import discord
from discord.ext import commands

os.chdir(os.path.dirname(os.path.abspath(__file__)))
if __name__ == '__main__':
    bot = RedditBotManager()
    bot.run(os.getenv('DISCORD_TOKEN')) 
    # @bot.event
    #
        
    # @bot.command()
    # async def test(ctx, *args):
    #     print("command called")
    #     print(ctx.channel)
    #     print(ctx.author)
    #     print(ctx.message) 
    #     arguments = ', '.join(args)
    #     await ctx.send(f'{len(args)} arguments: {arguments}')

    # @bot.command()
    # async def add(ctx, left : int, right : int):
    #     """Adds two numbers together."""
    #     await ctx.send(left + right)

    

