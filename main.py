import os
import json
import asyncio

import PIL
import aiohttp
import aiofiles
import asyncclick

from PIL import Image
from pathlib import Path

from database import Manga
from database import Helper

from rich.table import Table
from tqdm.asyncio import tqdm
from rich.prompt import Prompt
from rich.console import Console

from urllib.parse import urljoin
from selectolax.parser import HTMLParser

console = Console()


class Scraper(Helper):
    def __init__(self, url: str, domain_name: str, chapter_number: int = 0):
        self.url = url
        self.details = {}
        self.domain_name = domain_name
        self.chapter_number = chapter_number
        self.resolved_path = Path(f"downloads/{self.domain_name}").resolve()
        self.css_selectors = {
            "flamecomics": {
                "title": 'h1[class="entry-title"]',
                "cover": "div.thumb img",
                "cover_attr": "src",
                "li": "li[data-num] a",
                "chapter": "span.chapternum",
                "attr": "href",
                "pages": 'div[class="rdminimal"] img',
                "page_attr": "src",
            },
            "asurascans": {
                "title": 'h1[class="entry-title"]',
                "cover": "div.thumb img",
                "cover_attr": "src",
                "li": "div.eph-num a",
                "chapter": "span.chapternum",
                "attr": "href",
                "pages": 'div[class="rdminimal"] img',
                "page_attr": "src",
            },
            "manga18": {
                "title": "h1",
                "author": ".author-content a",
                "artist": ".artist-content a",
                "genre": ".genres-content a",
                "description": ".ss-manga",
                "cover": "div.summary_image img",
                "cover_attr": "src",
                "li": 'li[class="a-h wleft"] a',
                "chapter": 'li[class="a-h wleft"] a',
                "attr": "href",
                "pages": 'div[class="read-content wleft"] img',
                "page_attr": "src",
            },
            "manhwascan": {
                "title": "h1",
                "cover": "div.summary_image img",
                "cover_attr": "src",
                "li": 'li[class="a-h"] a',
                "chapter": 'li[class="a-h"] a',
                "attr": "href",
                "pages": 'div[class="read-content wleft"] img',
                "page_attr": "src",
            },
            "manhuascan": {
                "title": 'h1[class="entry-title"]',
                "cover": 'div[class="thumb"] img',
                "cover_attr": "src",
                "li": "li[data-num] a",
                "chapter": 'span[class="chapternum"]',
                "attr": "href",
                "pages": "div#readerarea img",
                "page_attr": "src",
            },
        }
        self.HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
        }

    @staticmethod
    def clean_string(string: str) -> str:
        text = " ".join(filter(None, string.split("\n")))
        bad_chars = ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]
        return "".join(x for x in text if x not in bad_chars)

    def create_details_json(self, json_data: dict[str, str]) -> None:
        with open(
            self.resolved_path / self.title / "details.json", "w", encoding="UTF-8"
        ) as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)

    async def fetch_chapters(
        self, session: aiohttp.ClientSession, css_selectors: dict[str, str]
    ) -> list[tuple]:
        async with session.get(self.url) as response:
            tree = HTMLParser(await response.text())
            self.title = Scraper.clean_string(
                tree.css_first(css_selectors["title"]).text(strip=True)
            )
            self.cover = tree.css_first(css_selectors["cover"]).attributes[
                css_selectors["cover_attr"]
            ]

            # values = tree.css('.post-content_item')[2:]
            # author = values[1].text(strip=True).split(':')[1]
            # artist = values[2].text(strip=True).split(':')[1]
            # description = values[0].css_first('.entry-content').text(strip=True) or None
            # genre = [i.strip() for i in list(filter(None, values[3].text().split('\n')))[1:]]
            # url = f'https://{"".join(filter(None, self.url.split("/")[2]))}{v.attributes[css_selectors["attr"]]}

            self.details = {
                "title": self.title,
                "author": "author",
                "artist": "artist",
                "description": "description",
                "genre": "genre",
                "status": "0",
                "_status values": [
                    "0 = Unknown",
                    "1 = Ongoing",
                    "2 = Completed",
                    "3 = Licensed",
                    "4 = Publishing finished",
                    "5 = Cancelled",
                    "6 = On hiatus",
                ],
            }

            chapters = []
            for v in tree.css(css_selectors["li"]):
                try:
                    chapter = Scraper.clean_string(
                        v.css_first(css_selectors["chapter"]).text(strip=True)
                    )
                except AttributeError:
                    chapter = Scraper.clean_string(v.text(strip=True))
                url = urljoin(self.url, v.attributes[css_selectors["attr"]])
                chapters.append((chapter, url))
            console.print(f" Total chapters: {len(chapters)}")
            return chapters[::-1]

    async def fetch_pages(
        self, session: aiohttp.ClientSession, url: str, css_selectors: dict[str, str]
    ) -> list[str | None]:
        async with session.get(url, headers=self.HEADERS) as response:
            tree = HTMLParser(await response.text())
            page_title = tree.css_first(css_selectors["title"]).text(strip=True)
            pages = [
                pg.attributes[css_selectors["page_attr"]]
                for pg in tree.css(css_selectors["pages"])
            ]

            console.print("[yellow]=" * 50)
            console.print(
                f"[bright bold white] TITLE[/bright bold white] : {page_title}"
            )
            console.print(
                f"[bright bold white] URL[/bright bold white]   : [purple]{url}"
            )
            console.print(f" {len(pages)} [bright white]pages")

            return pages

    async def download_imgs(
        self, session: aiohttp.ClientSession, url: str, file_name: str, chapter: str
    ) -> None:
        _title_path = self.resolved_path / self.title
        chapter_path = _title_path / f"_{chapter}".replace("\t", "")
        file_path = chapter_path / file_name
        chapter_path.mkdir(parents=True, exist_ok=True)

        if not (_title_path / "details.json").exists():
            self.create_details_json(self.details)

        if not (
            cover := self.resolved_path
            / self.title
            / f'cover.{self.cover.split(".")[-1]}'
        ).exists():
            async with session.get(self.cover) as response:
                async with aiofiles.open(cover, mode="wb") as f:
                    await f.write(await response.read())

        try:
            if file_path.exists():
                with Image.open(file_path) as img:
                    img.verify()
                with Image.open(file_path) as img:
                    img.load()
        except PIL.UnidentifiedImageError:
            os.remove(file_path)
        except OSError:
            os.remove(file_path)

        if not file_path.exists():
            async with session.get(url) as response:
                chunk_size = response.content.iter_chunked(1024)
                total_size = response.headers.get("content-length")
                async with aiofiles.open(file_path, mode="wb") as f:
                    async for chunk in tqdm(
                        iterable=chunk_size, total=int(total_size) / 1024, unit="KB"
                    ):
                        await f.write(chunk)

    async def tasks(
        self, session: aiohttp.ClientSession, urls: list[str | None], chapter: str
    ) -> None:
        try:
            async with asyncio.TaskGroup() as tg:
                for key, url in enumerate(urls, start=1):
                    tg.create_task(
                        self.download_imgs(
                            session=session,
                            url=url,
                            file_name=f'{key:03}.{url.split(".")[-1]}',
                            chapter=chapter,
                        )
                    )
        except* Exception as e:
            console.print(e.exceptions)

    async def controller(self, css_selectors: dict[str, str]) -> None:
        timeout = aiohttp.ClientTimeout(total=None)
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(
            headers=self.HEADERS, timeout=timeout, connector=connector
        ) as session:
            chapters = await self.fetch_chapters(
                session=session, css_selectors=css_selectors
            )

            self._insert(title=self.title, url=self.url, domain_name=self.domain_name)

            if (n := self.chapter_number) is not None:
                chapters = chapters[int(n) - 1 :]

            for chapter, url in chapters:
                urls = await self.fetch_pages(
                    session=session, url=url, css_selectors=css_selectors
                )
                await self.tasks(session=session, urls=urls, chapter=chapter)


@asyncclick.command()
@asyncclick.argument("url", nargs=-1)
@asyncclick.option("--chapter-number", "-ch")
async def main(url: str, chapter_number: int) -> None:
    database = Helper()
    database.create_tables()

    if len(database.get_all()) == 0:
        url = Prompt.ask("|>> Enter url")

    if not url:

        table = Table(title="[bold white]Mangas")
        table.add_column("ID", justify="left", style="cyan", no_wrap=False)
        table.add_column("Title", style="magenta")
        table.add_column("Domain", style="green")
        table.add_column("Url", style="blue")

        for item in database.get_all().order_by(+Manga.title):
            table.add_row(str(item.id), item.title, item.domain_name, item.url)

        console.print(table)
        console.print("-" * 50)
        console.print("CTRL + C to exit at any time.", style="dim")
        console.print("-" * 50)

        _id = Prompt.ask("|>>")
        url = database.get(int(_id)).url

    console.clear()
    path = url.split("www.")[-1].split("//")[-1].split(".")[0]
    download = Scraper(url, path, chapter_number)

    if css_selector := download.css_selectors.get(path):
        await download.controller(css_selectors=css_selector)
    else:
        console.print("Site not [red]compatibale")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("[red]Keyboard interrupt[/red] received, [green]exiting[/green].")
