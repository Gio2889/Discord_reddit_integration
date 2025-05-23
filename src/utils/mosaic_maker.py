import aiohttp
import asyncio
import logging
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import matplotlib.pyplot as plt

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

async def fetch_image(session: aiohttp.ClientSession, url: str) -> Image.Image | None:
    """Fetches and opens a single image from a URL."""
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                try:
                    img = Image.open(BytesIO(data))
                    # Optional: Resize image here if a max dimension is desired early
                    # img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                    return img
                except UnidentifiedImageError:
                    logging.warning(f"Cannot identify image from URL: {url}. Content type: {response.headers.get('Content-Type')}")
                    return None
                except Exception as e:
                    logging.error(f"Error processing image data from {url}: {e}", exc_info=True)
                    return None
            else:
                logging.warning(f"Failed to fetch {url}. Status: {response.status}")
                return None
    except aiohttp.ClientError as e:
        logging.error(f"Network error fetching {url}: {e}", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"Unexpected error fetching image {url}: {e}", exc_info=True)
        return None

async def imager_puller(image_list: list[str]):
    """
    Fetch images from given URLs asynchronously using asyncio.gather.

    Args:
        image_list (list[str]): List of image URLs to fetch.

    Returns:
        list[Image.Image]: A list of successfully fetched and opened PIL Image objects.
                           Returns an empty list if no images could be fetched/processed.
    """
    if not image_list:
        logging.info("Empty image_list provided to imager_puller.")
        return []

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_image(session, url) for url in image_list]
        results = await asyncio.gather(*tasks) # Run all fetch operations concurrently
        
        # Filter out None results (failed fetches or processing)
        images = [img for img in results if img is not None]
        
        if not images:
            logging.warning("No images successfully fetched or processed from the provided list.")
        
        return images


async def mosaic_maker(image_list: list[str], max_dim: int = 1024):
    """
    Create a mosaic from a list of image URLs.
    Resizes images to a maximum dimension before creating the mosaic.

    Args:
        image_list (list[str]): List of image URLs.
        max_dim (int): Maximum dimension (width or height) for resizing images
                       before plotting to optimize performance.

    Returns:
        BytesIO | None: A bytes buffer of the saved composite image (PNG format),
                        or None if no images could be processed or an error occurs.
    """
    if not image_list:
        logging.warning("mosaic_maker received an empty image_list.")
        return None

    images_pil = await imager_puller(image_list)

    if not images_pil:
        logging.warning("imager_puller returned no images for mosaic_maker.")
        return None

    # Resize images
    resized_images = []
    for img in images_pil:
        try:
            # Create a copy to avoid modifying the original image object if it's cached or reused
            img_copy = img.copy() 
            img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            resized_images.append(img_copy)
        except Exception as e:
            logging.error(f"Error resizing image: {e}", exc_info=True)
    
    if not resized_images:
        logging.warning("No images were successfully resized.")
        return None
        
    images_to_plot = resized_images
    n = len(images_to_plot)

    if n > 4: # Limit to a maximum of 4 images for the mosaic
        images_to_plot = images_to_plot[:4]
        n = 4
    
    fig = None # Initialize fig to ensure it's available for plt.close(fig) in finally
    try:
        if n == 1:
            fig, ax = plt.subplots(1, 1, figsize=(5, 5)) # Smaller figsize for single image
            axes = [ax]
        elif n == 2:
            fig, axes = plt.subplots(1, 2, figsize=(10, 5)) # Rectangular for 2 images
        elif n == 3:
            fig = plt.figure(figsize=(10, 10))
            gs = fig.add_gridspec(2, 2)
            axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])]
        elif n == 4:
            fig, axes_array = plt.subplots(2, 2, figsize=(10, 10))
            axes = axes_array.flatten()
        else: # Should not happen due to earlier check, but as a safeguard
            logging.warning(f"Unexpected number of images ({n}) after filtering. Cannot create mosaic.")
            return None

        for ax, img in zip(axes, images_to_plot):
            ax.set_facecolor("none") # Make background transparent if image has alpha
            ax.imshow(img)
            ax.axis("off") # Remove axis ticks and labels

        # Adjust layout to prevent overlap if necessary.
        # For simple cases with axis('off'), tight_layout might not be strictly needed
        # but can help if there were titles or other elements.
        if fig: # Ensure fig is defined
             fig.tight_layout(pad=0.1)


        buf = BytesIO()
        # Save the figure to the buffer
        if fig: # Ensure fig is defined before saving
            fig.savefig(
                buf, format="png", bbox_inches="tight", pad_inches=0.0, transparent=True, dpi=150 # Adjust DPI as needed
            )
            buf.seek(0)
            return buf
        else:
            logging.error("Figure object was not created. Cannot save mosaic.")
            return None

    except Exception as e:
        logging.error(f"Error creating mosaic with matplotlib: {e}", exc_info=True)
        return None
    finally:
        if fig:
            plt.close(fig) # Ensure the figure is closed to free memory
        # plt.close('all') # Use if multiple figures might be open from other parts or errors
