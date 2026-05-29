import asyncio
from src.calendar import EconomicCalendar
from datetime import datetime, timezone, timedelta

async def test_cal():
    cal = EconomicCalendar()
    await cal.fetch_data()
    print(f"Total events found: {len(cal.events)}")
    for ev in cal.events:
        print(ev['dt'].isoformat(), ev['title'], ev['country'])
        
    # Simulate a fake event right now
    now = datetime.now(timezone.utc)
    fake_event = {
        'title': 'Test NFP',
        'country': 'USD',
        'dt': now + timedelta(minutes=15) # 15 minutes in the future
    }
    cal.events.append(fake_event)
    
    blocking = cal.get_current_blocking_event()
    print(f"Blocking event: {blocking}")

asyncio.run(test_cal())
