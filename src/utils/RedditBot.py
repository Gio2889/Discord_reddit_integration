import os
import discord
from discord.ext import tasks, commands
from utils.RedditMonitor import RedditMonitor

class RedditBotManager(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.typing = True
        intents.message_content = True
        self.reddit_monitor = RedditMonitor()
        self.post_channel = os.getenv('DISCORD_POST_CHANNEL')
        self.check_interval = int(os.getenv('CHECK_INTERVAL'))# 2 hours in seconds
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        await self.reddit_monitor.initialize()
        await self.reddit_monitor.get_subred()
        print("subreddit inital scan performed")
        print(f"These are the posts:\n {self.reddit_monitor.processed_posts}")
    
    async def on_ready(self):
        print(f'We have logged in as {self.user}')
        await self.add_cog(CommandGroup(self))

    async def close(self):
        await self.reddit_monitor.close()  # This assumes that RedditMonitor has a close_session method
        await super().close() 

class CommandGroup(commands.Cog):
    @commands.command(name="hello")
    async def hello(self, ctx):
        await ctx.send("Hello I am a bot.")

    @commands.command()
    async def test(self,ctx, *args):
        print("command called")
        print(ctx.channel)
        print(ctx.author)
        print(ctx.message) 
        arguments = ', '.join(args)
        await ctx.send(f'{len(args)} arguments: {arguments}')

    @commands.command()
    async def checknow(self,ctx):
        """Manually trigger Reddit check"""
        await ctx.send("Checking for new posts...")
        await self.reddit_monitor.get_subred()
        print("Scan subreddit performed")
        print(f"These are the posts:\n {self.reddit_monitor.processed_posts}")
    #     await self.post_reddit_updates()

    #async def on_message(message):
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


    

    # def format_reddit_post(self, content):
    #     """Convert Reddit content to Discord-friendly format"""
    #     if "**Link:** http" in content:
    #         url = content.split("**Link:** ")[1]
    #         if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
    #             return None, url  # Return separate image URL
    #     return discord.Embed(description=content), None

    # @tasks.loop(seconds=int(os.getenv('CHECK_INTERVAL')))
    # async def post_reddit_updates(self):
    #     channel = self.get_channel(self.post_channel_id)
    #     if not channel:
    #         return

    #     new_posts = await self.reddit_monitor.get_subred()
    #     for post_content in new_posts:
    #         try:
    #             embed, image_url = self.format_reddit_post(post_content)
                
    #             if image_url:
    #                 await channel.send(image_url)
    #             elif embed:
    #                 await channel.send(embed=embed)
                
    #             await asyncio.sleep(5)  # Rate limit protection
    #         except Exception as e:
    #             print(f"Failed to post content: {e}")

    # @post_reddit_updates.before_loop
    # async def before_post_updates(self):
    #     await self.wait_until_ready()

    # async def close(self):
    #     await self.reddit_monitor.close()
    #     await super().close()

