import os
import asyncpraw
import asyncio
import aiofiles
from aiohttp import ClientSession
from dotenv import load_dotenv
# import requests
# import time
# from openai import OpenAI
#load env variables
load_dotenv()

# Define class for the bot
class RedditMonitor():
    def __init__(self):
        self.processed_posts = set() # initialize set
        self.load_processed_posts()
        self.session = None
        self.reddit = None
        self.max_retries = 3
        self.subreddit_name=os.getenv('SUBREDDIT_NAME')
        self.target_flairs=os.getenv('TARGET_FLAIRS')
        print(self.target_flairs)

    def _build_flair_query(self, flairs: str) -> str:
        """Build Reddit search query from flair list
            comma separated str
        """
        if not flairs:
            return None
        flairs = flairs.split(",")
        escaped_flairs = [f'flair:"{flair}"' for flair in flairs]
        
        if len(escaped_flairs) == 1:
            return escaped_flairs[0]
        return f'({" OR ".join(escaped_flairs)})'

    async def initialize(self):
        self.session = ClientSession(trust_env=True)
        self.reddit = asyncpraw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT'),
            usename=os.getenv('REDDIT_USERNAME'),
            password=os.getenv('REDDIT_PASSWORD'),
            requestor_kwargs={"session": self.session},  # pass the custom Session instance
            )

    async def get_subred(self, target_flair: bool = False):
        if not self.reddit:
            await self.initialize() # if reddit is not ready call initialization
        retries = 0
        while retries < self.max_retries:
            try:
                content = {}
                subreddit = await self.reddit.subreddit(os.getenv('SUBREDDIT_NAME')) 
                search_query = self._build_flair_query(self.target_flairs)
                async for submission in subreddit.search(
                                                        query=search_query,
                                                        sort='new',
                                                        limit=20,
                                                        time_filter='all'
                                                    ):
                    try:
                        # if the post is not in the proceessed post list
                        if submission.id not in self.processed_posts:
                            self.processed_posts.add(submission.id)
                            content[submission.id] =  await self.get_post_content(submission)
                        
                        #content process will hapenned here
                            
                    except Exception as e:
                        print(f"Error processing post {submission.id}: {e}")
                        break
                await self.save_processed_posts()
                return content
            except Exception as api_error:
                print(f"API error encountered: {api_error}")
                break

    async def get_post_content(self, submission):
            print("post found")
            content = f"**Title:** {submission.title}\n"
            if submission.is_self:
                content += f"**Text:** {submission.selftext}"  
            else:
                content += f"**Link:** {submission.url}"

    async def save_processed_posts(self):
        try:
            with aiofiles.open('processed_posts.txt', 'w') as f:
                f.writelines(f"{post_id}\n" for post_id in self.processed_posts)
                print("print lines")
        except Exception as e:
            print(f"Error saving processed posts:\n {e}")

    def load_processed_posts(self):
        try:
            with open('processed_posts.txt', 'r') as f:
                self.processed_posts = set(f.read().splitlines())
        except FileNotFoundError: # if no posts are saved, continue without error
            pass
    
    async def close(self):
        if self.session:
            await  self.session.close()
        
async def main():
    monitor =  RedditMonitor() 
    try:
        await monitor.get_subred()
        print(monitor.processed_posts)
    finally:
        await monitor.close()
