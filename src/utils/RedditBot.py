import os
import discord
from discord.ext import commands, tasks
from utils.RedditMonitor import RedditMonitor
from utils.mosaic_maker import mosaic_maker


class RedditBotManager(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.typing = True
        intents.message_content = True
        self.reddit_monitor = RedditMonitor()
        self.post_channel = os.getenv("DISCORD_POST_CHANNEL")
        self.check_interval = int(os.getenv("CHECK_INTERVAL"))  # 2 hours in seconds
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.reddit_monitor.initialize()
        await self.reddit_monitor.get_subred()
        print("subreddit inital scan performed")

    async def on_ready(self):
        print(f"We have logged in as {self.user}")
        await self.add_cog(CommandGroup(self.reddit_monitor))

    async def close(self):
        await (
            self.reddit_monitor.close()
        )  # This assumes that RedditMonitor has a close_session method
        await super().close()


class CommandGroup(commands.Cog):
    def __init__(self, reddit_monitor):
        self.reddit_monitor = reddit_monitor

    @commands.command(name="hello")
    async def hello(self, ctx):
        await ctx.send("Hello I am a bot.")

    @commands.command()
    async def checknow(self, ctx):
        """Manually trigger Reddit check"""
        await ctx.send("Checking for new posts...")
        await self.reddit_monitor.get_subred()
        await self.publish_content(self.reddit_monitor.post_content, ctx)
        # after get subreddit runs the content of the latest posts is up and can be grabbed by the post_content method

    async def publish_content(self, post_content: dict, ctx):
        for post_id, content_str in post_content.items():
            parsed_content = await self.parse_reddit_post(content_str)
            if "Images" in parsed_content:
                embedVar, attachment_file = await self.embed_gallery(parsed_content)
                await ctx.send(embed=embedVar, file=attachment_file)
            else:
                embedVar = await self.embed_post(parsed_content)
                await ctx.send(embed=embedVar)

    async def embed_gallery(self, parsed_content: dict):
        # Create main embed
        embedVar = discord.Embed(
            title=parsed_content["Title"],
            description="New post has been found",
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
            description="New post has been found",
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
