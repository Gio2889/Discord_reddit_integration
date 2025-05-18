import os
import discord
import csv
from discord.ext import commands, tasks
from utils.RedditMonitor import RedditMonitor
from utils.mosaic_maker import mosaic_maker
from utils.SB_connector import SupabaseConnector


class RedditBotManager(commands.Bot):
    """A class to manage a Reddit Bot that interacts with a Discord server."""

    def __init__(self, Supabase: bool = False):
        """Initializes the RedditBotManager with Discord intents and settings.

        Args:
            Supabase (bool): Whether to initialize Supabase connector.
        """
        intents = discord.Intents.default()
        intents.messages = True
        intents.typing = True
        intents.message_content = True
        self.auto_post = True  # Automatically post updates
        self.reddit_monitor = RedditMonitor()  # Reddit monitoring instance
        if Supabase:
            self.supabase = SupabaseConnector()  # Initialize Supabase if needed
        else:
            self.supabase = None
        self.post_channel = int(
            os.getenv("DISCORD_POST_CHANNEL")
        )  # Channel ID for posting
        self.check_interval = 20  # Default check interval
        self.command_group = None  # Command group placeholder
        self.check_interval = int(
            os.getenv("CHECK_INTERVAL")
        )  # Update check interval from environment
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """Runs before the bot is ready. Override to implement custom setup."""
        pass

    async def on_ready(self):
        """Triggered when the bot has successfully connected and is ready.

        This function sets up the command group, initializes the Reddit monitor,
        and starts scheduled tasks for automatic posting.
        """
        print(f"We have logged in as {self.user}")
        print("Bot ready")
        # Updating class defaults after the bot initiates
        self.post_channel = self.get_channel(self.post_channel)
        self.command_group = CommandGroup(
            self.reddit_monitor, self.supabase, self.post_channel
        )
        await self.add_cog(self.command_group)  # Add command group to the bot

        # Initializing Reddit Monitor
        print("Initializing Reddit Monitor")
        await self.reddit_monitor.initialize()

        # Start automatic updates if enabled
        if self.auto_post:
            self.checknow_task.change_interval(seconds=self.check_interval)
            self.checknow_task.start()

    async def on_message(self, message):
        """Handles incoming messages in the monitored channel.

        Args:
            message (discord.Message): The received message object.
        """
        if message.channel.id == self.post_channel.id:
            # Check if message has attachments or embeds and no GIFs
            if (
                message.attachments or message.embeds
            ) and "gif" not in message.content.lower():
                emoji_name_list = [
                    "rate_0",
                    "CherryTomato",
                    "GreenPepper",
                    "YellowPepper",
                    "CarolinaReaper",
                    "FIRE",
                ]
                # Fetch emojis by names
                emoji_list = [
                    await self.command_group.get_emoji_by_name(message, emoji_name)
                    for emoji_name in emoji_name_list
                ]
                await self.command_group.add_reactions_to_message(
                    message,
                    emoji_list,  # Add reactions to the message
                )

        # Ensure other commands still work
        await super().on_message(message)

    @tasks.loop(seconds=20)
    async def checknow_task(self):
        """Scheduled task to execute checks every specified interval."""
        if self.post_channel:
            await self.command_group.execute_checknow(self.post_channel)
        else:
            print("Channel not found.")

    checknow_task.before_loop

    async def before_checknow_task(self):
        """Waits until the bot is ready before executing the checknow task."""
        await self.wait_until_ready()

    async def close(self):
        """Closes the bot and stops scheduled tasks."""
        self.checknow_task.stop()  # Stop the scheduled task
        await self.reddit_monitor.close()  # Close Reddit monitor gracefully
        await super().close()  # Close the bot


class CommandGroup(commands.Cog):
    """
    Handle Reddit monitoring and interaction through Discord.

    Args:
        reddit_monitor: Instance of RedditMonitor to monitor Reddit posts.
        supabase: Instance of SupabaseConnector for database interaction.
        authorised_channel: The Discord channel authorized for bot interaction.

    Returns:
        None
    """

    def __init__(self, reddit_monitor, supabase, authorised_channel):
        self.reddit_monitor = reddit_monitor
        self.supabase = supabase
        if self.supabase:
            # switch to local doc for tracking post
            self.posted_ids = self.supabase.database_ids
        else:
            self.posted_ids = self._get_local_ids()

        self.published_posts = []
        self.authorised_channel = authorised_channel

    @commands.command(name="hello")
    async def hello(self, ctx):
        """
        Respond to a hello command.

        Args:
            ctx: The context of the command invocation.

        Returns:
            None
        """
        await ctx.send("Hello I am a bot.")

    @commands.command()
    async def checknow(self, ctx):
        """Manually trigger Reddit check"""
        if ctx.channel.id != self.authorised_channel.id:
            await ctx.send("Im not authorized to publish in this channel")
        """
        Manually trigger the Reddit check for new posts.

        Args:
            ctx: The context of the command invocation.

        Returns:
            None
        Raises:
            discord.Forbidden: If the command attempts to run in an unauthorized channel.
        """
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
        """
        Publish content to a Discord channel based on Reddit posts.

        Args:
            post_content (dict): A dictionary where keys are post IDs and values are content strings.
            ctx: The context from which the command was invoked, providing the channel to send messages.

        Returns:
            None

        Raises:
            Any exceptions related to Discord API or content processing.
        """
        # List of emoji names used for reactions
        emoji_name_list = [
            "rate_0",
            "CherryTomato",
            "GreenPepper",
            "YellowPepper",
            "CarolinaReaper",
            "FIRE",
        ]
        emoji_list = [
            await self.get_emoji_by_name(ctx, emoji_name)
            for emoji_name in emoji_name_list
        ]
        for post_id, content_str in post_content.items():
            if post_id not in self.posted_ids:
                parsed_content = await self.parse_reddit_post(content_str)
                if 'Link' not in list(parsed_content.keys()): # no link available; skip
                    continue
                if "Images" in parsed_content:
                    embedVar, attachment_file = await self.embed_gallery(parsed_content)
                    if embedVar:
                        message = await ctx.send(embed=embedVar, file=attachment_file)
                else:
                    embedVar = await self.embed_post(parsed_content)
                    if embedVar:
                        message = await ctx.send(embed=embedVar)
                if message: #if post was succesfully posted
                    await self.add_reactions_to_message(message, emoji_list)
                    self.published_posts.append(
                        {
                            "id": post_id,
                            "title": parsed_content["Title"],
                            "author": parsed_content["Author"],
                        }
                    )
        if self.supabase:
            self.supabase.insert_entries(self.published_posts)
        else:
            self.update_posted_ids()

    async def embed_gallery(self, parsed_content: dict):
        """
        Create an embed for a gallery of images from a Reddit post.

        Args:
            parsed_content (dict): The parsed content from the Reddit post containing images.

        Returns:
            embedVar: A Discord embed object.
            composite_file: A Discord file object of the combined images, or None if no images.

        Raises:
            Any exceptions related to image processing.
        """
        try:
            embedVar = discord.Embed(
                title=parsed_content["Title"],
                description=f"New post by {parsed_content['Author']}",
                url=parsed_content["Link"],
                color=0x00FF00,
            )
        except KeyError as e:
            print(f"Missing key in parsed content: {e}")
            print(f"Item Content: {parsed_content}")
            return None,None
        except Exception as e:
            print(f"error creating embeded content;\n{e}")
            print(f"Item Content: {parsed_content}")
            return None,None
        
        image_list = parsed_content["Images"].split(" ")

        # Fetch images and create a composite if necessary
        buf = await mosaic_maker(image_list)
        if buf:
            composite_file = discord.File(buf, filename="combined.png")
            embedVar.set_image(url="attachment://combined.png")
        else:
            composite_file = None
        return embedVar, composite_file

    async def embed_post(self, parsed_content):
        """
        Create an embed for a single post.

        Args:
            parsed_content: The parsed content of the Reddit post.

        Returns:
            embedVar: A Discord embed object.

        Raises:
            Any exceptions related to the embed creation.
        """
        try:
            embedVar = discord.Embed(
                title=parsed_content["Title"],
                description=f"New post by {parsed_content['Author']}",
                url=parsed_content["Link"],
                color=0x00FF00,
            )
            embedVar.set_image(url=parsed_content["Link"])
            return embedVar
        except Exception as e:
            print('Error creating embed content')
            return None
        
        
        

    async def parse_reddit_post(self, content):
        """
        Parse a Reddit post string into a structured dictionary.

        Args:
            content (str): The raw content of the Reddit post.

        Returns:
            results (dict): A dictionary with parsed data from the post.

        Raises:
            Any exceptions related to content formatting.
        """
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

    async def get_emoji_by_name(self, ctx, emoji_name):
        """
        Get a custom emoji object from a guild by its name.

        Args:
            ctx: The context from which the emoji is fetched.
            emoji_name (str): Name of the emoji to find.

        Returns:
            emoji: The custom emoji object if found; otherwise None.

        Raises:
            None
        """
        guild = ctx.guild
        if guild:
            for emoji in guild.emojis:
                if emoji.name == emoji_name:
                    return emoji
        return None

    async def add_reactions_to_message(self, message, emoji_list):
        """
        Add a list of emoji reactions to a specified message.

        Args:
            message: The message object to which reactions will be added.
            emoji_list (list): A list of emoji objects to react with.

        Returns:
            None

        Raises:
            Any exceptions related to the Discord API.
        """
        for emoji in emoji_list:
            await message.add_reaction(emoji)

    def _get_local_ids(self):
        """
        Get a list of posted IDs from the local posted_ids.csv file.

        Returns:
            ids (list): A list of posted IDs.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        ids = []
        file_path = "posted_ids.csv"

        if os.path.exists(file_path):
            with open(file_path, mode="r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                ids = [row["id"] for row in reader]
        return ids

    def update_posted_ids(self):
        """
        Update posted_ids.csv with the current published posts.

        Returns:
            None

        Raises:
            Any exceptions related to file writing.
        """
        file_path = "posted_ids.csv"
        fieldnames = ["id", "title", "author"]

        file_mode = "a" if os.path.exists(file_path) else "w"

        with open(file_path, mode=file_mode, newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            if file_mode == "w":
                writer.writeheader()

            for post in self.published_posts:
                writer.writerow(
                    {"id": post["id"], "title": post["title"], "author": post["author"]}
                )

        for post in self.published_posts:
            self.posted_ids.append(post["id"])
