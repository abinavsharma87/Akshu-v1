import asyncio
import os
import re
import json
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
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        # Use yt-dlp for more reliable info extraction
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                title = info.get('title', 'No Title')
                duration_sec = info.get('duration', 0)
                duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
                thumbnail = f"https://img.youtube.com/vi/{info['id']}/maxresdefault.jpg"
                vidid = info['id']
                
                # Fallback to VideosSearch if needed
                if not all([title, duration_sec, thumbnail]):
                    results = VideosSearch(link, limit=1)
                    result = (await results.next())["result"][0]
                    title = result["title"]
                    duration_min = result["duration"]
                    duration_sec = int(time_to_seconds(duration_min))
                    thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                    vidid = result["id"]
                
                return title, duration_min, duration_sec, thumbnail, vidid
        except Exception as e:
            print(f"Error getting details: {e}")
            # Fallback to VideosSearch if yt-dlp fails
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            title = result["title"]
            duration_min = result["duration"]
            duration_sec = int(time_to_seconds(duration_min))
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        details = await self.details(link, videoid)
        return details[0] if details else None

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        details = await self.details(link, videoid)
        return details[1] if details else None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        details = await self.details(link, videoid)
        return details[3] if details else None

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        # Enhanced format selection
        ydl_opts = {
            'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]',
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                if 'url' in info:
                    return 1, info['url']
                return 0, "No direct URL found"
        except Exception as e:
            return 0, str(e)

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
            
        ydl_opts = {
            'extract_flat': True,
            'playlistend': limit,
            'quiet': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
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

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        ytdl_opts = {
            'quiet': True,
            'listformats': True
        }
        
        formats_available = []
        try:
            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                for format in info.get('formats', []):
                    try:
                        if not format.get('video_ext') == 'none' and not format.get('audio_ext') == 'none':
                            formats_available.append({
                                "format": format.get('format'),
                                "filesize": format.get('filesize'),
                                "format_id": format.get('format_id'),
                                "ext": format.get('ext'),
                                "format_note": format.get('format_note'),
                                "yturl": link,
                            })
                    except:
                        continue
        except Exception as e:
            print(f"Formats error: {e}")
            
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
            
        results = VideosSearch(link, limit=10)
        result = (await results.next()).get("result")[query_type]
        return (
            result["title"],
            result["duration"],
            result["thumbnails"][0]["url"].split("?")[0],
            result["id"]
        )

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
        if videoid:
            link = self.base + link
            
        loop = asyncio.get_running_loop()
        
        def audio_dl():
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'downloads/%(id)s.%(ext)s',
                'quiet': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'prefer_ffmpeg': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                path = ydl.prepare_filename(info)
                if not path.endswith('.mp3'):
                    new_path = os.path.splitext(path)[0] + '.mp3'
                    os.rename(path, new_path)
                    path = new_path
                return path

        def video_dl():
            ydl_opts = {
                'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]',
                'outtmpl': 'downloads/%(id)s.%(ext)s',
                'quiet': True,
                'merge_output_format': 'mp4',
                'prefer_ffmpeg': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                return ydl.prepare_filename(info)

        def song_video_dl():
            ydl_opts = {
                'format': f'{format_id}+bestaudio',
                'outtmpl': f'downloads/{title}.mp4',
                'quiet': True,
                'merge_output_format': 'mp4',
                'prefer_ffmpeg': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            return f'downloads/{title}.mp4'

        def song_audio_dl():
            ydl_opts = {
                'format': format_id,
                'outtmpl': f'downloads/{title}.%(ext)s',
                'quiet': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'prefer_ffmpeg': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            return f'downloads/{title}.mp3'

        if songvideo:
            path = await loop.run_in_executor(None, song_video_dl)
            return path
        elif songaudio:
            path = await loop.run_in_executor(None, song_audio_dl)
            return path
        elif video:
            if await is_on_off(1):
                downloaded_file = await loop.run_in_executor(None, video_dl)
                direct = True
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "-g",
                    "-f",
                    "best[height<=720]",
                    link,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")[0]
                    direct = False
                else:
                    downloaded_file = await loop.run_in_executor(None, video_dl)
                    direct = True
        else:
            downloaded_file = await loop.run_in_executor(None, audio_dl)
            direct = True
            
        return downloaded_file, direct
