import os
import discord
import json
from datetime import datetime,timedelta,timezone
from discord.ext import commands, tasks
from utils.RedditMonitor import RedditMonitor
from utils.mosaic_maker import mosaic_maker
from utils.SB_connector import SupabaseConnector
import requests
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
        self.supabase = None
        #self.supabase = SupabaseConnector()
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

    def _decompose_attachment(self,data: str) -> str:
        """
        Decomposes a string representation of an attachment into a JSON-like format.
        
        Args:
            data (str): The input string containing attachment information.
            
        Returns:
            str: A JSON-like string representation of the attachment.
        """
        # Extracting the information
        id_start = data.find('id=') + len('id=')
        id_end = data.find(' ', id_start)
        id_value = data[id_start:id_end].strip()

        filename_start = data.find('filename=\'') + len('filename=\'')
        filename_end = data.find('\'', filename_start)
        filename_value = data[filename_start:filename_end].strip()

        url_start = data.find('url=\'') + len('url=\'')
        url_end = data.find('\'', url_start)
        url_value = data[url_start:url_end].strip()

        # Creating the JSON structure
        json_data = {
            "Attachment": {
                "id": id_value,
                "filename": filename_value,
                "url": url_value
            }
        }
        # Return the JSON string
        return json_data
        #return json.dumps(json_data, indent=2)

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

    @commands.command(name="fetch")
    async def fetch_images_reactions(self, ctx, days: int):
        """Fetch all images and reactions from the last 'days' days."""
        print("Fetching images")
        #uncomment later
        # if ctx.channel.id != self.authorised_channel.id:
        #     await ctx.send("I'm not authorized to retrieve messages from this channel.")
        #     return

        # Calculate the cut-off time
        cut_off_time = datetime.now(timezone.utc) - timedelta(days=days)
        image_reactions = {}
        rating_dict = {}
        async for message in ctx.history(limit=None): # Adjust limit as necessary
            if message.created_at > cut_off_time:
                reactions = await self.collect_reactions(message)  # Collect reactions
                rating = await self.rate_image(reactions)
                
                if rating != '-': # image was rated on the scale ie good image 
                    if message.embeds:  # Check if there are embed
                        l=0
                        for embed in message.embeds: 
                            if embed.image.url is not None:
                                if embed.type == 'rich' and embed.image.url.endswith((".jpg",".jpeg",".png",".webp")):
                                    extention = embed.image.url.split(".")[-1].split("/")[-1]
                                    type = f"image/{extention}"
                                    image_url = embed.url 
                                    image_reactions[message.id]={
                                        'file' : embed.title,
                                        'image_url': image_url,
                                        'reactions': reactions,
                                        'type' :type
                                    }
                                    await self.download_image(str(message.id),str(l),image_url,extention,'D:/DiscordBotTrainingSet/images')
                                    extention= type.split("/")[-1]        
                                    rating_dict[f"{message.id}_{l}.{extention}"] = rating
                            l+1

                    if message.attachments: # Check if there are attachements
                        l=0
                        for attachment in message.attachments:
                            #attachment_info = self._decompose_attachment(attachment)
                            filename = attachment.filename
                            image_url = attachment.url
                            type = attachment.content_type
                            if type == 'image/gif':
                                continue
                            else:
                                extention = attachment.content_type.split("/")[-1]
                                await self.download_image(str(message.id),str(l),image_url,extention,'D:/DiscordBotTrainingSet/images')
                            image_reactions[message.id] = {
                                        'file' : filename,
                                        'image_url': image_url,
                                        'reactions': reactions,
                                        'type' :  type
                                    }
                            extention= type.split("/")[-1]        
                            rating_dict[f"{message.id}_{l}.{extention}"] = rating
                            l+=1
                            
                    
                        
        # Send a summary of images and their reactions
        if rating_dict:
            #await ctx.send(f"Found {len(image_reactions)} images in the last {days} days.")
            print(f"Found {len(rating_dict)} images in the last {days} days.")
            with open('D:/DiscordBotTrainingSet/scores.json','w') as f:
                json.dump(rating_dict,f,indent=4)
                #await ctx.send(f"Image: {item['image_url']}\nReactions: {item['reactions']}")
        else:
            print(f"No images found in the last {days} days.")
            #await ctx.send(f"No images found in the last {days} days.")

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

    async def collect_reactions(self, message):
            """Collects reaction counts from the given message."""
            reaction_data = {}
            for reaction in message.reactions:
                reaction_data[reaction.emoji] = reaction.count
            return reaction_data
    
    async def download_image(self, id: str ,idx:str, image_url: str, extention: str,output_path : str= "downloaded_images"):
        # Download the image
        filename = os.path.join(output_path, f"{id}_{idx}.{extention}")
        if os.path.isfile(filename):
            print(f'File with id: {id} already exists. Skipping download.')
            return
        # Get the image content
        response = requests.get(image_url)
        if response.status_code == 200:
            # Save the image to a file
            filename = os.path.join(output_path,f"{id}_{idx}.{extention}")
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f'Downloaded file with id: {id}_{idx}')
        else:
            print('Failed to download image.')\
            
    async def rate_image(self,emoji_dict : dict,scale : dict = None):
        if scale is None:
            scale = {
                'FIRE' : 10,
                'CarolinaReaper' : 8,
                'YellowPepper' : 6,
                'GreenPepper' : 4,
                'CherryTomato': 2,
                'rate_0': 0
            };
        valid_emojis = [key for key in scale.keys()]
        rating_sum, count = 0, 0
        
        # Check if all emojis in scale are present in emoji_dict
        all_emojis_present = all(emoji in emoji_dict for emoji in valid_emojis)

        for emoji, emoji_counts in emoji_dict.items():
            if hasattr(emoji, 'name') and emoji.name in valid_emojis:
                # If all emojis are present, skip counting for the first appearance
                if all_emojis_present and count == 0:
                    emoji_counts-=1  # We we
                
                rating_sum += emoji_counts * scale[emoji.name]
                count += emoji_counts

        if count == 0:
            if emoji_dict.get('rate_0', 0) > 0:  # Check for 'rate_0' emoji count
                return 0
            return "-"  # Return "-" for no valid emojis
        else: 
            return rating_sum / count
                

