from __future__ import annotations

import random
from pathlib import Path


class ContentLoader:
    """Загружает тексты и картинки из папки content/."""

    IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}

    def __init__(self, content_dir: Path, photos_per_post: int) -> None:
        self.content_dir = content_dir
        self.photos_per_post = photos_per_post
        self.content_dir.mkdir(parents=True, exist_ok=True)
        (self.content_dir / "texts").mkdir(exist_ok=True)
        (self.content_dir / "images").mkdir(exist_ok=True)

    def pick_post(self) -> tuple[str, list[Path]]:
        texts_dir = self.content_dir / "texts"
        images_dir = self.content_dir / "images"

        texts = list(texts_dir.glob("*.txt"))
        text = ""
        if texts:
            text = random.choice(texts).read_text(encoding="utf-8").strip()

        images: list[Path] = []
        if self.photos_per_post > 0:
            all_images = [
                p for p in images_dir.iterdir()
                if p.is_file() and p.suffix.lower() in self.IMAGE_EXT
            ]
            if all_images:
                count = min(self.photos_per_post, 10, len(all_images))
                images = random.sample(all_images, count)

        return text, images
