import os
import discord
import csv
from discord.ext import commands, tasks
from utils.RedditMonitor import RedditMonitor
from utils.mosaic_maker import mosaic_maker
from utils.SB_connector import SupabaseConnector


class RedditBotManager(commands.Bot):
    def __init__(self, Supabase: bool =True):
        intents = discord.Intents.default()
        intents.messages = True
        intents.typing = True
        intents.message_content = True
        self.auto_post = True
        self.reddit_monitor = RedditMonitor()
        if Supabase:
            self.supabase = SupabaseConnector()
        else:
            self.supabase = None
        self.post_channel = int(
            os.getenv("DISCORD_POST_CHANNEL")
        )  # has been changed to ID
        self.check_interval = 20
        self.command_group = None
        # self.check_interval = int(os.getenv("CHECK_INTERVAL"))  # 2 hours in seconds
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """This fucntion runs before on-ready"""
        pass

    async def on_ready(self):
        print(f"We have logged in as {self.user}")
        print("Bot ready")
        # updating class defaults after the bot initiates
        self.post_channel = self.get_channel(self.post_channel)
        self.command_group = CommandGroup(
            self.reddit_monitor, self.supabase, self.post_channel
        )
        await self.add_cog(self.command_group)

        # get reddit post informations
        print("Initializing Reddit Monitor")
        await self.reddit_monitor.initialize()

        # switch to trigger automatic updates
        # TEST: check to see if starting the tasks run the loop
        if self.auto_post:
            self.checknow_task.change_interval(seconds=self.check_interval)
            self.checknow_task.start()

    @tasks.loop(seconds=20)
    async def checknow_task(self):
        if self.post_channel:
            await self.command_group.execute_checknow(self.post_channel)
        else:
            print("Channel not found.")

    checknow_task.before_loop

    async def before_checknow_task(self):
        await self.wait_until_ready()

    async def close(self):
        self.checknow_task.stop()
        await self.reddit_monitor.close()
        await super().close()


class CommandGroup(commands.Cog):
    def __init__(self, reddit_monitor, supabase, authorised_channel):
        self.reddit_monitor = reddit_monitor
        self.supabase = supabase
        if self.supabase:
            #switch to local doc for tracking post
            self.posted_ids = self.supabase.database_ids
        else:
            self.posted_ids = self._get_local_id()

        self.published_posts = []
        self.authorised_channel = authorised_channel

    
    @commands.command(name="hello")
    async def hello(self, ctx):
        await ctx.send("Hello I am a bot.")

    @commands.command()
    async def checknow(self, ctx):
        """Manually trigger Reddit check"""
        if ctx.channel.id != self.authorised_channel.id:
            await ctx.send("Im not authorized to publish in this channel")
            return
        await self.execute_checknow(ctx)

    async def execute_checknow(self, ctx):
        """Logic for check now. With this separation can now be called outside."""
        await ctx.send("Checking for new posts...")
        await self.reddit_monitor.get_posts()

        # update processed post and post contents
        self.reddit_monitor.processed_posts = set(
            [
                post
                for post in self.reddit_monitor.processed_posts
                if post not in self.posted_ids 
            ]
        )

        self.reddit_monitor.post_content = {
            post_id: content
            for post_id, content in self.reddit_monitor.post_content.items()
            if post_id not in self.posted_ids
        }

        # break out if there are no new posts
        if not self.reddit_monitor.post_content:
            await ctx.send("No new content to process.")
            return

        await self.publish_content(self.reddit_monitor.post_content, ctx)
        # repopulate the database_ids after it gets edited by publish_content
        if self.supabase:
            self.supabase.database_ids = self.supabase.get_post_ids()


    async def publish_content(self, post_content: dict, ctx):
        emoji_name_list = ["rate_0","CherryTomato","GreenPepper","YellowPepper","CarolinaReaper","FIRE"]
        emoji_list = [self.get_emoji_by_name(ctx,emoji_name) for emoji_name in emoji_name_list]
        for post_id, content_str in post_content.items():
            if post_id not in self.published_posts:
                parsed_content = await self.parse_reddit_post(content_str)
                if "Images" in parsed_content:
                    embedVar, attachment_file = await self.embed_gallery(parsed_content)
                    message = await ctx.send(embed=embedVar, file=attachment_file)
                else:
                    embedVar = await self.embed_post(parsed_content)
                    message = await ctx.send(embed=embedVar)
                self.add_reactions_to_message(message,emoji_list)
                self.published_posts.append(
                    {
                        "id": post_id,
                        "title": parsed_content["Title"],
                        "author": parsed_content["Author"],
                    }
                )
        if self.supabase:
            # update supabase here
            self.supabase.insert_entries(self.published_posts)
        else:
            self.update_posted_ids()

    async def embed_gallery(self, parsed_content: dict):
        # Create main embed
        embedVar = discord.Embed(
            title=parsed_content["Title"],
            description=f"New post by {parsed_content['Author']}",
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
            description=f"New post by {parsed_content['Author']}",
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

    async def get_emoji_by_name(ctx, emoji_name):
        """Get a custom emoji object from a guild by its name."""
        guild = ctx.guild
        if guild:
            for emoji in guild.emojis:
                if emoji.name == emoji_name:
                    return emoji
        return None

    async def add_reactions_to_message(message, emoji_list):
        """Add a list of emoji reactions to a message."""
        for emoji in emoji_list:
            await message.add_reaction(emoji)

    def _get_local_ids(self):
        """Get a list of posted IDs from the local posted_ids.csv file."""
        ids = []
        file_path = 'posted_ids.csv'

        # Check if the file exists to prevent FileNotFoundError
        if os.path.exists(file_path):
            with open(file_path, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                ids = [row["id"] for row in reader]  # Assumes the column name is 'id'
        return ids

    def update_posted_ids(self):
        """Update posted_ids.csv with the current published posts."""
        file_path = 'posted_ids.csv'
        # Ensure the published_posts are being recorded
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            fieldnames = ['id', 'title', 'author']
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            writer.writeheader()  # Write header for the CSV
            for post in self.published_posts:
                writer.writerow({ 
                    'id': post["id"],
                    'title': post["title"],
                    'author': post["author"]
                })