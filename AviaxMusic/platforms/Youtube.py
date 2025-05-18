import asyncio
import os
import re
import time
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from AviaxMusic.utils.database import is_on_off
from AviaxMusic.utils.formatters import time_to_seconds

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.last_request_time = 0
        self.request_delay = 1.5  # 1.5 second delay between requests

    async def _rate_limit(self):
        """Enforce rate limiting to avoid bot detection"""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def _get_ydl_opts(self, audio_only=True):
        """Get optimized yt-dlp options without cookies"""
        return {
            'format': 'bestaudio/best' if audio_only else 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'force_ipv4': True,
            'socket_timeout': 15,
            'retries': 3,
            'extractor_args': {'youtube': {'skip': ['dash', 'hls']}},
            'postprocessor_args': {'ffmpeg': ['-loglevel', 'quiet']},
            'outtmpl': 'downloads/%(id)s.%(ext)s',
        }

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        await self._rate_limit()
        
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        # Handle search queries
        if not any(link.startswith(x) for x in ('http://', 'https://', 'ytsearch:')):
            link = f"ytsearch:{link}"
            
        ydl_opts = self._get_ydl_opts()
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, link, download=False)
                
                if 'entries' in info:  # Handle search results
                    info = info['entries'][0]
                    
                title = info.get('title', 'No Title')
                duration_sec = info.get('duration', 0)
                duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
                vidid = info.get('id', '')
                thumbnail = f"https://img.youtube.com/vi/{vidid}/maxresdefault.jpg"
                
                return title, duration_min, duration_sec, thumbnail, vidid
                
        except Exception as e:
            print(f"YT-DLP Error: {e}")
            # Fallback to VideosSearch
            try:
                results = VideosSearch(link if not link.startswith('ytsearch:') else link[9:], limit=1)
                result = (await results.next())["result"][0]
                title = result["title"]
                duration_min = result["duration"]
                duration_sec = int(time_to_seconds(duration_min))
                thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                vidid = result["id"]
                return title, duration_min, duration_sec, thumbnail, vidid
            except Exception as e:
                print(f"VideosSearch Error: {e}")
                return "Unknown Title", "0:00", 0, "", ""

    async def title(self, link: str, videoid: Union[bool, str] = None):
        details = await self.details(link, videoid)
        return details[0] if details else "Unknown Title"

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        details = await self.details(link, videoid)
        return details[1] if details else "0:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        details = await self.details(link, videoid)
        return details[3] if details else ""

    async def video(self, link: str, videoid: Union[bool, str] = None):
        await self._rate_limit()
        
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        ydl_opts = self._get_ydl_opts(audio_only=False)
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, link, download=False)
                if 'url' in info:
                    return 1, info['url']
                return 0, "No direct URL found"
        except Exception as e:
            return 0, str(e)

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        await self._rate_limit()
        
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
            
        ydl_opts = self._get_ydl_opts()
        ydl_opts['playlistend'] = limit
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, link, download=False)
                if 'entries' in info:
                    return [entry['id'] for entry in info['entries']]
                return []
        except Exception as e:
            print(f"Playlist error: {e}")
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        details = await self.details(link, videoid)
        if not details:
            return None, None
            
        title, _, duration_min, thumbnail, vidid = details
        yturl = f"https://youtu.be/{vidid}"
        
        return {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        await self._rate_limit()
        
        if videoid:
            link = self.base + link
            
        loop = asyncio.get_running_loop()
        ydl_opts = self._get_ydl_opts(audio_only=not video)
        
        if songvideo or songaudio:
            ydl_opts['outtmpl'] = f'downloads/{title}.%(ext)s'
            if songvideo:
                ydl_opts['format'] = f'{format_id}+bestaudio'
                ydl_opts['merge_output_format'] = 'mp4'
            else:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if songvideo or songaudio:
                    await loop.run_in_executor(None, lambda: ydl.download([link]))
                    ext = 'mp4' if songvideo else 'mp3'
                    return f'downloads/{title}.{ext}'
                else:
                    path = await loop.run_in_executor(None, lambda: ydl.extract_info(link, download=True))
                    path = ydl.prepare_filename(path)
                    if not video and not path.endswith('.mp3'):
                        new_path = os.path.splitext(path)[0] + '.mp3'
                        os.rename(path, new_path)
                        path = new_path
                    return path, True
        except Exception as e:
            print(f"Download error: {e}")
            return None, False
