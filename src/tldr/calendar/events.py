"""Event detection and calendar link generation."""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DetectedEvent:
    """An event detected from email text."""

    name: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    location: str
    calendar_link: str


def detect_events(text: str) -> list[DetectedEvent]:
    """
    Detect events from summarized email text.
    
    Looks for the format:
    Event Detected: [Event Name] on [YYYY-MM-DD] at [HH:MM] at [Location]
    
    Args:
        text: Text to search for events.
        
    Returns:
        List of detected events.
    """
    pattern = r"Event Detected:\s*(.+?)\s+on\s+(\d{4}-\d{2}-\d{2})\s+at\s+(\d{2}:\d{2})\s+at\s+(.+?)(?:\n|$)"
    matches = re.findall(pattern, text)

    events = []
    for match in matches:
        event_name, event_date, event_time, event_location = match
        
        calendar_link = generate_calendar_link(
            name=event_name.strip(),
            date=event_date,
            time=event_time,
            location=event_location.strip(),
        )

        events.append(
            DetectedEvent(
                name=event_name.strip(),
                date=event_date,
                time=event_time,
                location=event_location.strip(),
                calendar_link=calendar_link,
            )
        )

    return events


def generate_calendar_link(
    name: str,
    date: str,
    time: str,
    location: str,
    duration_hours: int = 1,
) -> str:
    """
    Generate a Google Calendar link for an event.
    
    Args:
        name: Event name.
        date: Event date (YYYY-MM-DD).
        time: Event time (HH:MM).
        location: Event location.
        duration_hours: Event duration in hours.
        
    Returns:
        Google Calendar URL.
    """
    # Parse and format dates
    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt.replace(hour=start_dt.hour + duration_hours)

    # Format for Google Calendar (YYYYMMDDTHHmmssZ)
    start_str = start_dt.strftime("%Y%m%dT%H%M00")
    end_str = end_dt.strftime("%Y%m%dT%H%M00")

    # URL encode parameters
    params = {
        "action": "TEMPLATE",
        "text": name,
        "dates": f"{start_str}/{end_str}",
        "details": name,
        "location": location,
    }

    query_string = urllib.parse.urlencode(params)
    return f"https://calendar.google.com/calendar/render?{query_string}"


def replace_events_with_links(text: str) -> str:
    """
    Replace event detection blocks with clickable calendar links.
    
    Args:
        text: Text containing Event Detected blocks.
        
    Returns:
        Text with events replaced by HTML calendar links.
    """
    events = detect_events(text)
    result = text

    for event in events:
        event_block = (
            f"Event Detected: {event.name} on {event.date} "
            f"at {event.time} at {event.location}"
        )

        html_link = (
            f'<a target="_blank" rel="noopener" href="{event.calendar_link}" '
            f'style="background-color: #F4D66C; font-size: 18px; '
            f'font-family: Helvetica, Arial, sans-serif; font-weight:bold; '
            f'text-decoration: none; padding: 14px 20px; color: #1D2025; '
            f'border-radius: 5px; display:inline-block;">'
            f'📅 Add to Google Calendar: {event.name}</a>'
        )

        result = result.replace(event_block, html_link)

    return result
