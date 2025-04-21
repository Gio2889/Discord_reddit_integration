import os
import discord
from datetime import datetime,timedelta,timezone
from discord.ext import commands, tasks
from utils.RedditMonitor import RedditMonitor
from utils.mosaic_maker import mosaic_maker
from utils.SB_connector import SupabaseConnector



class RedditBotManager(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.typing = True
        intents.message_content = True
        intents.emojis_and_stickers = True
        intents.reactions = True
        self.auto_post = True
        self.reddit_monitor = RedditMonitor()
        self.supabase = SupabaseConnector()
        self.post_channel = int(
            os.getenv("DISCORD_POST_CHANNEL")
        )  # has been changed to ID
        self.check_interval = 7200
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

    @commands.command(name="fetch_images_reactions")
    async def fetch_images_reactions(self, ctx, days: int):
        """Fetch all images and reactions from the last 'days' days."""
        if ctx.channel.id != self.authorised_channel.id:
            await ctx.send("I'm not authorized to retrieve messages from this channel.")
            return

        # Calculate the cut-off time
        cut_off_time = datetime.now(timezone.utc) - timedelta(days=3)
        print(cut_off_time)
        image_reactions = []
        messages=[]
        async for message in ctx.channel.history(limit=100): # Adjust limit as necessary
            messages.append(
                {
                "msg" : message.content,
                "timestmp" : message.created_at,
                "reactions" : message.reactions,
                "attch" : message.attachments,
                "embeds" : message.embeds,
                "pic link" : message.content.endswith((".jpg",".jpeg",".png"))
                }
            )
            if message.created_at > cut_off_time:
                if message.embeds:  # Check if there are embeds
                    for embed in message.embeds:
                        if str(embed.url).endswith
                        print(dir(embed))
                        print(f"{message.id} is wihtin the time frame and has an embed")
                        print(embed.type)
                        print(embed.url)
                        print(embed.title)
                        print(embed.set_image)
                        if embed.type == 'image':
                            
                            image_url = embed.url  # Get image URL
                            reactions = self.collect_reactions(message)  # Collect reactions
                            image_reactions.append({
                                'image_url': image_url,
                                'reactions': reactions
                            })

        # Send a summary of images and their reactions
        if image_reactions:
            await ctx.send(f"Found {len(image_reactions)} images in the last {days} days.")
            for item in image_reactions:
                await ctx.send(f"Image: {item['image_url']}\nReactions: {item['reactions']}")
        else:
            await ctx.send(f"No images found in the last {days} days.")
        # [print(f"{message}\n") for  message in messages]

    async def execute_checknow(self, ctx):
        """Logic for check now. With this separation can now be called outside."""
        await ctx.send("Checking for new posts...")
        await self.reddit_monitor.get_posts()

        # update processed post and post contents
        self.reddit_monitor.processed_posts = set(
            [
                post
                for post in self.reddit_monitor.processed_posts
                if post not in self.supabase.database_ids
            ]
        )

        self.reddit_monitor.post_content = {
            post_id: content
            for post_id, content in self.reddit_monitor.post_content.items()
            if post_id not in self.supabase.database_ids
        }

        # break out if there are no new posts
        if not self.reddit_monitor.post_content:
            await ctx.send("No new content to process.")
            return

        await self.publish_content(self.reddit_monitor.post_content, ctx)
        # repopulate the database_ids after it gets edited by publish_content
        self.supabase.database_ids = self.supabase.get_post_ids()

    async def publish_content(self, post_content: dict, ctx):
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
                        "id": post_id,
                        "title": parsed_content["Title"],
                        "author": parsed_content["Author"],
                    }
                )
        # update supabase here
        self.supabase.insert_entries(self.published_posts)

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

    def collect_reactions(self, message):
            """Collects reaction counts from the given message."""
            reaction_data = {}
            for reaction in message.reactions:
                reaction_data[reaction.emoji] = reaction.count
            return reaction_data