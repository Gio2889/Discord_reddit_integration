import os
import discord
from discord.ext import commands, tasks
from discord.utils import get
from utils.RedditMonitor import RedditMonitor
from utils.mosaic_maker import mosaic_maker


class RedditBotManager(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.typing = True
        intents.message_content = True
        self.auto_post = False 
        self.reddit_monitor = RedditMonitor()
        self.post_channel = int(os.getenv("DISCORD_POST_CHANNEL")) #has been changed to ID
        self.check_interval = 20
        self.command_group = None
        #self.check_interval = int(os.getenv("CHECK_INTERVAL"))  # 2 hours in seconds
        super().__init__(command_prefix="!", intents=intents)
        

    async def setup_hook(self):
        """This fucntion runs before on-ready"""
        pass
    

    async def on_ready(self):
        print(f"We have logged in as {self.user}")
        print("Bot ready")
        self.command_group = CommandGroup(self.reddit_monitor)
        await self.add_cog(self.command_group)
        print("Initializing Reddit Monitor")
        await self.reddit_monitor.initialize()
        await self.reddit_monitor.get_posts()
        print("Post gathered")

        self.post_channel = self.get_channel(self.post_channel)
        if self.post_channel:
            await self.command_group.execute_checknow(self.post_channel)
        else:
            print("Channel not found.")

        # switch to trigger automatic updates
        if self.auto_post:
            self.checknow_task.change_interval(seconds=self.check_interval)
            self.checknow_task.start()

    @tasks.loop(seconds=20)
    async def checknow_task(self):
        print("check will be run here")
        if self.post_channel:
            await self.commandgroup.execute_checknow(self.post_channel)
        else:
            print("Channel not found.")

    checknow_task.before_loop
    async def before_checknow_task(self):
        print("from before the loop")
        await self.wait_until_ready() 

    async def close(self):
        self.checknow_task.stop()
        await ( self.reddit_monitor.close() )  
        await super().close()



class CommandGroup(commands.Cog):
    def __init__(self, reddit_monitor):
        self.reddit_monitor = reddit_monitor
        self.published_posts = []

    @commands.command(name="hello")
    async def hello(self, ctx):
        await ctx.send("Hello I am a bot.")

    @commands.command()
    async def checknow(self, ctx):
        """Manually trigger Reddit check"""
        await self.excecute_checknow(ctx)

    async def execute_checknow(self,ctx):
        """Logic for check now. With this separation can now be called outside."""
        await ctx.send("Checking for new posts...")
        await self.reddit_monitor.get_posts()
        await self.publish_content(self.reddit_monitor.post_content, ctx)

        # after get subreddit runs the content of the latest posts is up and can be grabbed by the post_content method

    async def publish_content(self, post_content: dict, ctx):
        if ctx.channel != 823034880710672394:
            ctx.send("Im not authorized to publish in this channel")
            return
        for post_id, content_str in post_content.items():
            if post_id not in self.published_posts:
                parsed_content = await self.parse_reddit_post(content_str)
                if "Images" in parsed_content:
                    embedVar, attachment_file = await self.embed_gallery(parsed_content)
                    await ctx.send(embed=embedVar, file=attachment_file)
                else:
                    embedVar = await self.embed_post(parsed_content)
                    await ctx.send(embed=embedVar)
                self.published_posts.append(
                        {
                            'id' : post_id,
                            'title' : parsed_content["Title"],
                            'author' : parsed_content["Author"]
                        }
                        )
        # update supabase here

    async def embed_gallery(self, parsed_content: dict):
        # Create main embed
        embedVar = discord.Embed(
            title=parsed_content["Title"],
            description=f"New post by {parsed_content["Author"]}",
            url=parsed_content["Link"],
            color=0x00FF00,
        )
        # embedVar.add_field(name="Post", value=, inline=False)
        image_list = parsed_content["Images"].split(" ")

        # Fetch images
        buf = await mosaic_maker(image_list)
        if buf:
            # Attach composite image to embed
            composite_file = discord.File(buf, filename="combined.png")
            embedVar.set_image(url="attachment://combined.png")
        else:
            composite_file = None
        return embedVar, composite_file

    async def embed_post(self, parsed_content):
        embedVar = discord.Embed(
            title=parsed_content["Title"],
            description=f"New post by {parsed_content["Author"]}",
            url=parsed_content["Link"],
            color=0x00FF00,
        )
        # embedVar.add_field(name ="Post", value=parsed_content["Title"], inline=False)
        embedVar.set_image(url=parsed_content["Link"])
        return embedVar

    async def parse_reddit_post(self, content):
        parts = content.split("**")
        results = {}
        current_key = None
        for part in parts:
            part = part.strip()
            if part:
                if current_key is None:
                    current_key = part
                else:
                    if current_key == "IMAGES":
                        image_urls = [url.strip() for url in part.split() if url]
                        results[current_key] = image_urls
                    else:
                        results[current_key] = part
                    current_key = None
        return results
