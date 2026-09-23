"""
WhatsApp chat export parser.

Parses the .txt file produced by WhatsApp's own "Export Chat" feature
(Settings > [chat] > Export Chat > Without Media) -- the only legitimate,
ToS-compliant way to get personal WhatsApp data into this system. There
is no official API for reading someone's personal chat history, and this
project does not attempt to work around that.
"""

import re
from dataclasses import dataclass
from datetime import datetime

_MESSAGE_LINE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s(\d{1,2}:\d{2}(?:\s?[APap][Mm])?)\s-\s([^:]+):\s(.*)$"
)
_SYSTEM_LINE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s(\d{1,2}:\d{2}(?:\s?[APap][Mm])?)\s-\s(.*)$"
)

_DATE_FORMATS = ["%d/%m/%Y", "%m/%d/%y", "%d/%m/%y", "%m/%d/%Y"]
_TIME_FORMATS = ["%H:%M", "%I:%M %p", "%I:%M%p"]


@dataclass
class WhatsAppMessage:
    timestamp: datetime | None
    sender: str
    text: str


class WhatsAppParseError(Exception):
    pass


def parse_export(raw_text: str) -> list[WhatsAppMessage]:
    lines = raw_text.splitlines()
    messages: list[WhatsAppMessage] = []

    for line in lines:
        match = _MESSAGE_LINE.match(line)
        if match:
            date_str, time_str, sender, text = match.groups()
            timestamp = _parse_timestamp(date_str, time_str)
            messages.append(WhatsAppMessage(timestamp=timestamp, sender=sender.strip(), text=text))
            continue

        system_match = _SYSTEM_LINE.match(line)
        if system_match:
            date_str, time_str, text = system_match.groups()
            timestamp = _parse_timestamp(date_str, time_str)
            messages.append(WhatsAppMessage(timestamp=timestamp, sender="(system)", text=text))
            continue

        if messages and line.strip():
            messages[-1].text += "\n" + line

    if not messages:
        raise WhatsAppParseError(
            "No messages found. Make sure this is a WhatsApp 'Export Chat > "
            "Without Media' .txt file -- other formats aren't supported."
        )

    return messages


def _parse_timestamp(date_str: str, time_str: str) -> datetime | None:
    for date_fmt in _DATE_FORMATS:
        for time_fmt in _TIME_FORMATS:
            try:
                return datetime.strptime(f"{date_str} {time_str}", f"{date_fmt} {time_fmt}")
            except ValueError:
                continue
    return None


def messages_to_chunks(messages: list[WhatsAppMessage], messages_per_chunk: int = 25) -> list[str]:
    chunks: list[str] = []
    for start in range(0, len(messages), messages_per_chunk):
        group = messages[start : start + messages_per_chunk]
        lines = []
        for m in group:
            when = m.timestamp.strftime("%Y-%m-%d %H:%M") if m.timestamp else "unknown time"
            lines.append(f"[{when}] {m.sender}: {m.text}")
        chunks.append("\n".join(lines))
    return chunks