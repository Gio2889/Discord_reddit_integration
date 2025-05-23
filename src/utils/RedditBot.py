import os
import discord
import csv
import logging
from discord.ext import commands, tasks
from .RedditMonitor import RedditMonitor
from .mosaic_maker import mosaic_maker
from .SB_connector import SupabaseConnector


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
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def setup_hook(self):
        """Runs before the bot is ready. Override to implement custom setup."""
        pass

    async def on_ready(self):
        """Triggered when the bot has successfully connected and is ready.

        This function sets up the command group, initializes the Reddit monitor,
        and starts scheduled tasks for automatic posting.
        """
        logging.info(f"We have logged in as {self.user}")
        logging.info("Bot ready")
        # Updating class defaults after the bot initiates
        self.post_channel = self.get_channel(self.post_channel)
        self.command_group = CommandGroup(
            self.reddit_monitor, self.supabase, self.post_channel
        )
        await self.add_cog(self.command_group)  # Add command group to the bot

        # Initializing Reddit Monitor
        logging.info("Initializing Reddit Monitor")
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
        # Do not process bot's own messages to prevent loops or unintended reactions to its own posts
        if message.author == self.user:
            return

        if message.channel.id == self.post_channel.id:
            # Check if message has attachments or embeds and no GIFs
            # Simplified condition: message has attachments OR (message has embeds AND not a GIF URL in common services)
            # This is a heuristic for "not a GIF". A more robust check might involve inspecting embed types or content_type.
            is_gif_url_in_embed = False
            if message.embeds:
                for embed in message.embeds:
                    if embed.url and ("giphy.com" in embed.url or "tenor.com" in embed.url or embed.url.endswith(".gif")):
                        is_gif_url_in_embed = True
                        break
                    if embed.image and embed.image.url and embed.image.url.endswith(".gif"):
                         is_gif_url_in_embed = True
                         break


            has_relevant_content = (message.attachments or message.embeds)
            is_not_gif = "gif" not in message.content.lower() and not is_gif_url_in_embed

            if has_relevant_content and is_not_gif:
                emoji_name_list = [
                    "rate_0", "CherryTomato", "GreenPepper", "YellowPepper",
                    "CarolinaReaper", "FIRE",
                ]
                # Fetch emojis by names using the message's channel as context for guild
                emoji_list = [
                    await self.command_group.get_emoji_by_name(message.channel, emoji_name)
                    for emoji_name in emoji_name_list
                ]
                # Filter out None emojis if any failed to fetch
                valid_emojis = [e for e in emoji_list if e]
                if valid_emojis:
                    await self.command_group.add_reactions_to_message(
                        message,
                        valid_emojis,  # Add reactions to the message
                    )
                else:
                    logging.warning(f"No valid emojis found to react to message {message.id} in {message.channel.name}")


        # Ensure other commands still work
        await super().on_message(message)

    @tasks.loop(seconds=20)
    async def checknow_task(self):
        """Scheduled task to execute checks every specified interval."""
        if self.post_channel:
            await self.command_group.execute_checknow(self.post_channel)
        else:
            logging.warning("Post channel not found for checknow task.")

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

    async def _create_post_embed(self, parsed_content: dict, is_gallery: bool = False):
        """Helper function to create a Discord embed for a Reddit post."""
        try:
            embed = discord.Embed(
                title=parsed_content["Title"],
                description=f"New post by {parsed_content['Author']}",
                url=parsed_content["Link"],
                color=0x00FF00,  # Green
            )
            if is_gallery:
                # For galleries, the image is set later after mosaic creation
                pass
            else:
                # For single image/link posts, set image directly if available
                # Assuming "Link" can be an image or a webpage. If it's a direct image link:
                embed.set_image(url=parsed_content["Link"])
            return embed
        except KeyError as e:
            logging.error(f"Missing key in parsed content for embed creation: {e}. Content: {parsed_content}")
            return None
        except Exception as e:
            logging.error(f"Error creating embed: {e}. Content: {parsed_content}")
            return None

    async def publish_content(self, post_content: dict, ctx):
        """
        Publish content to a Discord channel based on Reddit posts.

        Args:
            post_content (dict): A dictionary where keys are post IDs and values are content strings.
            ctx: The context (discord.ext.commands.Context or discord.TextChannel) 
                 for sending messages.

        Returns:
            None

        Raises:
            Any exceptions related to Discord API or content processing.
        """
        emoji_name_list = [
            "rate_0", "CherryTomato", "GreenPepper", "YellowPepper",
            "CarolinaReaper", "FIRE",
        ]
        # Determine the actual channel to send messages to, supporting both Context and TextChannel
        target_channel = ctx.channel if isinstance(ctx, commands.Context) else ctx
        if not target_channel:
            logging.error("Target channel is None, cannot publish content.")
            return

        emoji_list = [
            await self.get_emoji_by_name(target_channel, emoji_name) # Use target_channel for guild context
            for emoji_name in emoji_name_list
        ]
        # Filter out None emojis if any failed to fetch
        emoji_list = [e for e in emoji_list if e]


        for post_id, content_str in post_content.items():
            if post_id in self.posted_ids:
                logging.info(f"Post ID {post_id} already published. Skipping.")
                continue

            parsed_content = await self.parse_reddit_post(content_str)
            if not parsed_content or 'Link' not in parsed_content:
                logging.warning(f"Failed to parse content or missing link for post ID {post_id}. Skipping.")
                continue

            message_to_send = None
            attachment_file = None
            embed_var = None

            if "Images" in parsed_content and parsed_content["Images"]:
                embed_var = await self._create_post_embed(parsed_content, is_gallery=True)
                if embed_var:
                    image_list = parsed_content["Images"] # This is already a list from parse_reddit_post
                    if isinstance(image_list, str): # ensure it's a list
                        image_list = image_list.split(" ")
                    
                    buf = await mosaic_maker(image_list)
                    if buf:
                        attachment_file = discord.File(buf, filename="combined.png")
                        embed_var.set_image(url="attachment://combined.png")
                    else: # Mosaic creation failed, or no images after parsing
                        logging.warning(f"Mosaic maker failed for post ID {post_id}. Sending without gallery image.")
                        # Optionally, send without image or skip
                        # embed_var = await self._create_post_embed(parsed_content, is_gallery=False) # Fallback to non-gallery
            else:
                embed_var = await self._create_post_embed(parsed_content)

            if not embed_var:
                logging.error(f"Embed creation failed for post ID {post_id}. Skipping.")
                continue

            try:
                if attachment_file:
                    message_to_send = await target_channel.send(embed=embed_var, file=attachment_file)
                else:
                    message_to_send = await target_channel.send(embed=embed_var)
            except discord.Forbidden:
                logging.error(f"Bot lacks permissions to send messages in channel {target_channel.name} ({target_channel.id}). Post ID: {post_id}")
                continue # Skip this post
            except discord.HTTPException as e:
                logging.error(f"Failed to send message for post ID {post_id}: {e}. Status: {e.status}, Code: {e.code}")
                continue # Skip this post
            except Exception as e:
                logging.error(f"An unexpected error occurred while sending message for post ID {post_id}: {e}")
                continue


            if message_to_send:
                try:
                    await self.add_reactions_to_message(message_to_send, emoji_list)
                except Exception as e:
                    logging.error(f"Failed to add reactions to message for post ID {post_id}: {e}")

                self.published_posts.append({
                    "id": post_id,
                    "title": parsed_content.get("Title", "N/A"),
                    "author": parsed_content.get("Author", "N/A"),
                })

        if self.published_posts: #Only update if there are new posts
            if self.supabase:
                self.supabase.insert_entries(self.published_posts)
            else:
                self.update_posted_ids()
            self.published_posts.clear() # Clear after processing to avoid re-processing

    # Removed embed_gallery and embed_post as their logic is integrated into publish_content 
    # and _create_post_embed helper

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
        # ctx can be a Context object or a Channel object for on_message
        if isinstance(ctx, commands.Context):
            guild = ctx.guild
        elif isinstance(ctx, discord.TextChannel): # Added for on_message context
            guild = ctx.guild
        else: # Fallback or error if context is unexpected
            guild = None 
            logging.warning(f"Unexpected context type for get_emoji_by_name: {type(ctx)}")

        if guild:
            for emoji in guild.emojis:
                if emoji.name == emoji_name:
                    return emoji
        logging.warning(f"Emoji '{emoji_name}' not found in guild '{guild.name if guild else 'N/A'}'.")
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
        if not emoji_list: # Don't attempt if list is empty (e.g. all emojis failed to fetch)
            return
        for emoji in emoji_list:
            if emoji: # Ensure emoji object is valid
                try:
                    await message.add_reaction(emoji)
                except discord.Forbidden:
                    logging.error(f"Bot lacks permissions to add reactions in channel {message.channel.name} ({message.channel.id}). Emoji: {emoji.name}")
                    break # Stop trying if permissions are missing for one
                except discord.HTTPException as e:
                    logging.warning(f"Failed to add reaction {emoji.name}: {e}. Status: {e.status}, Code: {e.code}")
                except Exception as e:
                    logging.error(f"An unexpected error occurred while adding reaction {emoji.name}: {e}")
            else:
                logging.warning("Attempted to add a None emoji to a message.")


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
