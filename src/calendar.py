import asyncio
import logging
import aiohttp
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

class EconomicCalendar:
    def __init__(self):
        self.url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        self.events = []
        self.target_countries = ['USD', 'CNY']
        self.target_impacts = ['High']
        self.buffer_minutes = 30
        self.is_paused = False  # Menyimpan state untuk mencegah notifikasi berulang
        self.current_event = None
        self._running = True

    async def start(self):
        # Jalankan task background untuk update data setiap 12 jam
        asyncio.create_task(self._refresh_loop())

    async def _refresh_loop(self):
        while self._running:
            await self.fetch_data()
            await asyncio.sleep(12 * 3600)  # Sleep 12 jam

    async def fetch_data(self):
        try:
            async with aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0'}) as session:
                async with session.get(self.url, timeout=10) as resp:
                    if resp.status == 200:
                        # Some versions of aiohttp require content_type=None if server sends weird headers
                        data = await resp.json(content_type=None)
                        parsed_events = []
                        for item in data:
                            if item.get('country') in self.target_countries and item.get('impact') in self.target_impacts:
                                dt_str = item.get('date')
                                try:
                                    dt = datetime.fromisoformat(dt_str).astimezone(timezone.utc)
                                    parsed_events.append({
                                        'title': item.get('title'),
                                        'country': item.get('country'),
                                        'dt': dt
                                    })
                                except Exception as e:
                                    log.error(f"Error parsing date {dt_str}: {e}")
                        
                        self.events = sorted(parsed_events, key=lambda x: x['dt'])
                        log.info(f"📰 Kalender Ekonomi (USD/CNY High Impact) diperbarui: {len(self.events)} jadwal minggu ini.")
                    else:
                        log.error(f"Gagal mengambil kalender: HTTP {resp.status}")
        except Exception as e:
            log.error(f"Gagal koneksi ke API Kalender: {e}")

    def get_current_blocking_event(self) -> dict | None:
        """Mengembalikan data event jika saat ini berada di dalam zona bahaya (buffer)."""
        now = datetime.now(timezone.utc)
        for ev in self.events:
            # Skip if very old
            if now - ev['dt'] > timedelta(days=2):
                continue
                
            start_buffer = ev['dt'] - timedelta(minutes=self.buffer_minutes)
            end_buffer = ev['dt'] + timedelta(minutes=self.buffer_minutes)
            
            if start_buffer <= now <= end_buffer:
                return ev
        return None
