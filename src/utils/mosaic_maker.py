import aiohttp
from PIL import Image
from io import BytesIO
import matplotlib.pyplot as plt


async def imager_puller(image_list: list[str]):
    """
    Fetch images from given URLs asynchronously.

    Args:
        image_list (list[str]): List of image URLs to fetch.

    Returns:
        list[Image]: A list of PIL Image objects fetched from the URLs.

    Raises:
        Exception: If there is an error in fetching the image.
    """
    async with aiohttp.ClientSession() as session:
        images = []
        for url in image_list:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    img = Image.open(BytesIO(data))
                    images.append(img)
                else:
                    print(f"Failed to fetch {url}")
        return images


async def mosaic_maker(image_list: list[str]):
    """
    Create a mosaic from a list of image URLs.

    Args:
        image_list (list[str]): List of image URLs.

    Returns:
        BytesIO: A bytes buffer of the saved composite image.

    Raises:
        Exception: If there are no images provided.
    """
    images = await imager_puller(image_list)

    if images:
        n = len(images)
        if n > 4:
            images = images[:4]
            n = 4

        if n == 1:
            fig, axes = plt.subplots(1, 1, figsize=(10, 10))
            axes = [axes]
        elif n == 2:
            fig, axes = plt.subplots(1, 2, figsize=(10, 10))
        elif n == 3:
            fig = plt.figure(figsize=(10, 10))
            gs = fig.add_gridspec(2, 2)
            ax1 = fig.add_subplot(gs[0, 0])
            ax2 = fig.add_subplot(gs[0, 1])
            ax3 = fig.add_subplot(gs[1, :])
            axes = [ax1, ax2, ax3]
        elif n == 4:
            fig, axes = plt.subplots(2, 2, figsize=(10, 10))
            axes = axes.flatten()

        for ax, img in zip(axes, images):
            ax.set_facecolor("none")
            ax.imshow(img)
            ax.axis("off")

        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(
            buf, format="png", bbox_inches="tight", pad_inches=0, transparent=True
        )
        plt.close()
        buf.seek(0)
        return buf
    else:
        return
