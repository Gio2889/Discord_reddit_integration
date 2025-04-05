import os
import asyncpraw
import asyncio
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
        self.tgt_flairs=os.getenv('SUBREDDIT_NAME')

    def _build_flair_query(self, flairs: List[str]) -> str:
        """Build Reddit search query from flair list"""
        if not flairs:
            return None
        
        escaped_flairs = [f'flair:"{f.replace('"', '\\"')}"' for f in flairs]
        
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

    async def get_post_content(self, submission):
            content = f"**Title:** {submission.title}\n"
            if submission.is_self:
                content += f"**Text:** {submission.selftext}"  
            else:
                content += f"**Link:** {submission.url}"
            return content

    async def get_subred(self, target_flair: bool = False):
        if not self.reddit:
            await self.initialize() # if reddit is not ready call initialization
        
        retries = 0
        while retries < self.max_retries:
            try:
                subreddit = await self.reddit.subreddit(os.getenv('SUBREDDIT_NAME')) # get subreddit 
                #search_query = f'(flair:"Weapons/Armor Bsuild" OR flair:"Character Creation")'
                search_query = self._build_flair_query(self.target_flair)
                # test multiple subred and flairs here
                async for submission in subreddit.search(
                                                        query=search_query,
                                                        sort='new',
                                                        limit=10,
                                                        time_filter='all'
                                                    ):
                    try:
                        content = await self.get_post_content(submission)
                        print(f"New post: {content}")

                        #content process will hapenned here

                        if submission.id not in self.processed_posts:
                            self.processed_posts.add(submission.id)
                    except Exception as e:
                        print(f"Error processing post {submission.id}: {e}")
                break
            except (TooManyRequests, ServerError) as api_error:
                print(f"API error encountered: {api_error}")

    def load_processed_posts(self):
        try:
            with open('processed_posts.txt', 'r') as f:
                self.processed_posts = set(f.read().splitlines())
        except FileNotFoundError: # if not post are saved we keep going 
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

if __name__ == '__main__':
    asyncio.run(main())
    exit(0)
