import asyncio
import os
import random
import re
import time
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.last_request_time = 0
        self.request_delay = random.uniform(1.5, 3.0)  # Random delay between 1.5-3 seconds
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        ]

    async def _rate_limit(self):
        """Enforce random rate limiting to appear more human-like"""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()
        self.request_delay = random.uniform(1.5, 3.0)  # New random delay

    def _get_ydl_opts(self, audio_only=True):
        """Get optimized yt-dlp options with anti-detection measures"""
        return {
            'format': 'bestaudio/best' if audio_only else 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'force_ipv4': True,
            'socket_timeout': 30,
            'retries': 5,
            'fragment_retries': 5,
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'],
                    'player_client': ['android', 'web']
                }
            },
            'postprocessor_args': {'ffmpeg': ['-loglevel', 'quiet']},
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'user_agent': random.choice(self.user_agents),
            'referer': 'https://www.youtube.com/',
            'cookiefile': None,  # Explicitly no cookies
            'extract_flat': True,
            'throttled_rate': '1M',  # Limit download speed
            'sleep_interval_requests': random.randint(5, 10),
            'sleep_interval': random.randint(1, 3),
            'max_sleep_interval': 8,
        }

    async def _extract_with_retry(self, link, audio_only=True, retries=3):
        """Core extraction with advanced retry logic"""
        for attempt in range(retries):
            try:
                await self._rate_limit()
                ydl_opts = self._get_ydl_opts(audio_only)
                
                # Handle search queries
                if not any(link.startswith(x) for x in ('http://', 'https://', 'ytsearch:')):
                    link = f"ytsearch:{link}"
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = await asyncio.to_thread(ydl.extract_info, link, download=False)
                    return info
                    
            except Exception as e:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(random.uniform(1, 3))  # Random backoff

    async def details(self, link: str, videoid: Union[bool, str] = None):
        """Get video details with multiple fallback strategies"""
        try:
            if videoid:
                link = self.base + link
            
            # Try yt-dlp first
            info = await self._extract_with_retry(link)
            
            if info is None:
                raise Exception("No info returned")
                
            if 'entries' in info:  # Handle search results
                info = info['entries'][0]
                
            title = info.get('title', 'Unknown Title')
            duration_sec = info.get('duration', 0)
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            vidid = info.get('id', '')
            thumbnail = f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"
            
            return title, duration_min, duration_sec, thumbnail, vidid
            
        except Exception as e:
            print(f"YT-DLP failed, falling back to VideosSearch: {e}")
            try:
                # Fallback to VideosSearch
                clean_query = link.replace('ytsearch:', '') if link.startswith('ytsearch:') else link
                results = VideosSearch(clean_query, limit=1)
                result = (await results.next())["result"][0]
                return (
                    result["title"],
                    result["duration"],
                    int(result["duration"].split(':')[0]) * 60 + int(result["duration"].split(':')[1]),
                    result["thumbnails"][0]["url"].split("?")[0],
                    result["id"]
                )
            except Exception as e:
                print(f"All methods failed: {e}")
                return "Unknown Title", "0:00", 0, "", ""

    async def download(self, link: str, audio_only=True):
        """Download with enhanced anti-detection"""
        try:
            await self._rate_limit()
            ydl_opts = self._get_ydl_opts(audio_only)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, link, download=True)
                path = ydl.prepare_filename(info)
                
                if audio_only and not path.endswith('.mp3'):
                    new_path = os.path.splitext(path)[0] + '.mp3'
                    os.rename(path, new_path)
                    return new_path
                return path
                
        except Exception as e:
            print(f"Download failed: {e}")
            return None

    # [Keep all your other methods like url(), playlist(), etc. but use _extract_with_retry]
