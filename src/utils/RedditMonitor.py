import os
import asyncpraw
import aiofiles
import logging
import asyncio # Added for asyncio.sleep
from aiohttp import ClientSession
from dotenv import load_dotenv
from prawcore.exceptions import RequestException, ResponseException, OAuthException
from asyncpraw.exceptions import InvalidURL


class RedditMonitor:
    load_dotenv()

    def __init__(self):
        self.processed_posts = set()  # initialize set
        self.load_processed_posts()
        self.session = None
        self.reddit = None
        self.max_retries = 3  # Max retries for API calls
        self.post_content: dict = {}
        self.subreddit_names = os.getenv("SUBREDDIT_NAME")
        self.target_flairs = os.getenv("TARGET_FLAIRS")
        self.flair_query = self._build_flair_query(self.target_flairs)

    def _build_flair_query(self, flairs: str) -> str:
        """Build Reddit search query from flair list
        comma separated str
        """
        if not flairs:
            return None
        flairs = [flair.strip() for flair in flairs.split(",")] # Strip whitespace here
        escaped_flairs = [f'flair:"{flair}"' for flair in flairs if flair] # Ensure flair is not empty after strip

        if not escaped_flairs: # Handle case where all flairs were just spaces
            return None
        if len(escaped_flairs) == 1:
            return escaped_flairs[0]
        return f"({' OR '.join(escaped_flairs)})"

    async def initialize(self):
        self.session = ClientSession(trust_env=True)
        self.reddit = asyncpraw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT"),
            username=os.getenv("REDDIT_USERNAME"), # Corrected 'usename' to 'username'
            password=os.getenv("REDDIT_PASSWORD"),
            requestor_kwargs={
                "session": self.session
            },  # pass the custom Session instance
        )

    async def get_subred(self, subreddit_name: str, flair_query: str, limit: int = 2):
        if not self.reddit:
            await self.initialize()  # if reddit is not ready call initialization
        
        retries = 0
        while retries < self.max_retries:
            try:
                subreddit = await self.reddit.subreddit(subreddit_name)
                
                if flair_query is None:
                    logging.info(f"Fetching new posts from r/{subreddit_name} (limit={limit}) without flair.")
                    reddit_query = subreddit.new(limit=limit)
                else:
                    logging.info(f"Searching posts in r/{subreddit_name} with flair(s) '{flair_query}' (limit={limit}).")
                    reddit_query = subreddit.search(
                        query=flair_query,  # Use the passed flair_query, not self.flair_query directly
                        sort="new",
                        limit=limit,
                        time_filter="all", # Consider making time_filter configurable or shorter e.g. "day", "week"
                    )

                async for submission in reddit_query:
                    if submission.id in self.processed_posts:
                        logging.debug(f"Post {submission.id} already processed. Skipping.")
                        continue
                    
                    try:
                        content = await self.get_post_content(submission)
                        if content is None:
                            logging.warning(f"Content for post {submission.id} is None. Skipping.")
                            # Add to processed_posts even if content is None to avoid reprocessing if it's an issue with the post itself (e.g. video)
                            self.processed_posts.add(submission.id) 
                            continue
                        
                        self.post_content[submission.id] = content
                        self.processed_posts.add(submission.id)
                        logging.info(f"Successfully processed post {submission.id} from r/{subreddit_name}.")
                        
                    except Exception as e: # Catching specific post processing errors
                        logging.error(f"Error processing post {submission.id} in r/{subreddit_name}: {e}", exc_info=True)
                        # Decide if this post should be added to processed_posts to avoid retrying a problematic post
                        self.processed_posts.add(submission.id) 
                        # Depending on the error, you might choose to 'continue' to the next post or 'break' the loop.
                        # For now, let's continue to maximize content retrieval from the current batch.
                        continue 
                
                # await self.save_processed_posts() # Consider moving save to a less frequent operation (e.g. on close or periodically)
                return self.post_content # Return after successfully processing the batch
            
            except InvalidURL:
                logging.error(f"Invalid subreddit name format: r/{subreddit_name}. Skipping.")
                return self.post_content # Return current content, nothing new from this sub
            except (RequestException, ResponseException) as api_error: # More specific PRAW API errors
                retries += 1
                logging.warning(f"API error for r/{subreddit_name}: {api_error}. Retry {retries}/{self.max_retries}.")
                if retries >= self.max_retries:
                    logging.error(f"Max retries reached for r/{subreddit_name}. Skipping. Error: {api_error}", exc_info=True)
                    return self.post_content # Return current content
                await asyncio.sleep(5 * retries) # Exponential backoff
            except OAuthException as oauth_error:
                logging.error(f"OAuth authentication error for r/{subreddit_name}: {oauth_error}. Check credentials. Skipping.", exc_info=True)
                return self.post_content # Authentication error, likely won't resolve with retries
            except Exception as e: # Catch-all for other unexpected errors during subreddit fetch
                logging.error(f"Unexpected error when fetching posts from r/{subreddit_name}: {e}", exc_info=True)
                return self.post_content # Return current content
        
        return self.post_content # Should be reached if max_retries hit and loop exits, or other break conditions

    async def get_posts(self):
        if not self.subreddit_names:
            logging.warning("No subreddit names configured. Skipping get_posts.")
            return

        subreddit_list = self.subreddit_names.split(",")
        if len(subreddit_list) == 1:
            await self.get_subred(subreddit_list[0].strip(), self.flair_query)
        else:
            for subreddit_name in subreddit_list:
                # logging.info(f"Getting subreddit {subreddit_name.strip()}; flairs {self.flair_query}")
                await self.get_subred(subreddit_name.strip(), self.flair_query) # Pass self.flair_query here

    async def get_post_content(self, submission):
        try:
            await submission.load() # Ensures all attributes are loaded, can be costly.
                                 # Consider if all attributes are always needed or if some are optional.
            
            title = getattr(submission, 'title', 'N/A')
            author = getattr(submission, 'author', 'N/A') # Author object, consider author.name
            author_name = getattr(author, 'name', 'N/A') if author != 'N/A' else 'N/A'

            content = f"**Title** {title}\n"
            content += f"**Author** {author_name}\n"

            if getattr(submission, 'is_self', False):
                selftext = getattr(submission, 'selftext', '')
                content += f"**Text** {selftext if selftext else '[No text content]'}"
            elif getattr(submission, 'is_gallery', False):
                gallery_urls = []
                try:
                    # Ensure gallery_data and media_metadata are present
                    if not hasattr(submission, 'gallery_data') or not hasattr(submission, 'media_metadata'):
                        logging.warning(f"Post {submission.id} is marked as gallery but missing gallery_data or media_metadata.")
                        return None # Or handle as a simple link post if URL is available

                    for item in submission.gallery_data["items"]:
                        media_id = item["media_id"]
                        # Check if media_id exists in media_metadata
                        if media_id not in submission.media_metadata:
                            logging.warning(f"Media ID {media_id} not found in media_metadata for gallery post {submission.id}.")
                            continue 
                        
                        # Attempt to get the image URL, preferring higher resolution if available, fallback to 's'
                        image_info = submission.media_metadata[media_id].get("s", {}) # 's' for smaller preview
                        if 'u' in image_info: # uncompressed URL
                             gallery_urls.append(image_info["u"])
                        elif 'gif' in image_info: # sometimes gifs are here
                             gallery_urls.append(image_info["gif"])
                        else: # fallback or if other types are needed
                            logging.warning(f"No 'u' or 'gif' URL for media_id {media_id} in gallery post {submission.id}. Available: {submission.media_metadata[media_id].keys()}")


                    if gallery_urls:
                        content += f"**Link** {getattr(submission, 'url', '[No URL]')}\n" # Permalink to the post
                        content += "**Images** " + " ".join(gallery_urls)
                    else: # No valid image URLs found in gallery
                        logging.warning(f"Gallery post {submission.id} had no processable images.")
                        # Fallback to treating as a simple link post if desired, or return None
                        post_url = getattr(submission, 'url', None)
                        if post_url:
                            content += f"**Link** {post_url}"
                        else: # No images and no URL, this post might be problematic
                            return None
                except KeyError as e:
                    logging.error(f"KeyError accessing gallery data for post {submission.id}: {e}. Data: gallery_data={hasattr(submission, 'gallery_data')}, media_metadata={hasattr(submission, 'media_metadata')}", exc_info=True)
                    return None # Problematic gallery post
                except Exception as e: # Catch any other errors during gallery processing
                    logging.error(f"Unexpected error processing gallery for post {submission.id}: {e}", exc_info=True)
                    return None

            elif getattr(submission, 'is_video', False):
                logging.info(f"Post {submission.id} is a video. Skipping content generation as per policy.")
                return None # Explicitly return None for videos
            else: # Standard link post (not self, not gallery, not video)
                post_url = getattr(submission, 'url', None)
                if post_url:
                    content += f"**Link** {post_url}"
                else:
                    logging.warning(f"Post {submission.id} (type: link) has no URL. Title: {title}")
                    return None # No URL for a link post is usually an issue
            
            return content

        except AttributeError as e:
            logging.error(f"AttributeError accessing submission data for post {submission.id}: {e}", exc_info=True)
            return None
        except Exception as e: # Catch-all for any other unexpected error
            logging.error(f"Unexpected error in get_post_content for {submission.id}: {e}", exc_info=True)
            return None


    async def save_processed_posts(self):
        try:
            async with aiofiles.open("processed_posts.txt", "w") as f:
                await f.writelines(f"{post_id}\n" for post_id in self.processed_posts)
            logging.info("Successfully saved processed posts to processed_posts.txt.")
        except Exception as e:
            logging.error(f"Error saving processed posts: {e}", exc_info=True)

    def load_processed_posts(self):
        try:
            with open("processed_posts.txt", "r") as f:
                self.processed_posts = set(f.read().splitlines())
            logging.info(f"Loaded {len(self.processed_posts)} processed post IDs from processed_posts.txt.")
        except FileNotFoundError:
            logging.info("processed_posts.txt not found. Starting with an empty set of processed posts.")
            pass # Handled: no pre-existing file means no posts processed yet.
        except Exception as e:
            logging.error(f"Error loading processed posts: {e}", exc_info=True)
            # Decide if self.processed_posts should be empty or if the bot should halt.
            # For now, assume starting fresh is acceptable if loading fails.
            self.processed_posts = set()


    def clean_content(self):
        self.post_content = {}
        logging.debug("Post content dictionary cleared.")

    async def close(self):
        if self.reddit: # Attempt to save processed posts before closing
            await self.save_processed_posts() 
        if self.session:
            await self.session.close()
            logging.info("AIOHTTP ClientSession closed.")


# async def main():
#     monitor = RedditMonitor()
#     try:
#         await monitor.get_subred()
#         print(monitor.processed_posts)
#     finally:
#         await monitor.close()
