#!/usr/bin/env python3
"""Generate an SVG calendar by combining public GitHub contribution counts."""

from __future__ import annotations

import argparse
import html
import math
import re
import time
from collections import defaultdict
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GITHUB_USERNAME = re.compile(
    r"^(?=.{1,39}$)[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$"
)
COUNT_PATTERN = re.compile(r"([0-9][0-9,]*) contributions?")
MAX_RESPONSE_BYTES = 2_000_000
MIN_EXPECTED_DAYS = 300


class ContributionCalendarParser(HTMLParser):
    """Extract dates and contribution counts from GitHub's public calendar."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._dates_by_cell: dict[str, date] = {}
        self._tooltip_date: date | None = None
        self._tooltip_text: list[str] = []
        self.counts: dict[date, int] = {}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()

        if tag == "td" and "ContributionCalendar-day" in classes:
            cell_id = attributes.get("id")
            raw_date = attributes.get("data-date")
            if cell_id and raw_date:
                try:
                    self._dates_by_cell[cell_id] = date.fromisoformat(raw_date)
                except ValueError:
                    return

        if tag == "tool-tip":
            target = attributes.get("for")
            if target in self._dates_by_cell:
                self._tooltip_date = self._dates_by_cell[target]
                self._tooltip_text = []

    def handle_data(self, data: str) -> None:
        if self._tooltip_date is not None:
            self._tooltip_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "tool-tip" or self._tooltip_date is None:
            return

        tooltip = " ".join(self._tooltip_text).strip()
        match = COUNT_PATTERN.search(tooltip)
        if match:
            count = int(match.group(1).replace(",", ""))
        elif "No contributions" in tooltip:
            count = 0
        else:
            self._reset_tooltip()
            return

        self.counts[self._tooltip_date] = count
        self._reset_tooltip()

    def _reset_tooltip(self) -> None:
        self._tooltip_date = None
        self._tooltip_text = []


def validate_username(username: str) -> str:
    if not GITHUB_USERNAME.fullmatch(username):
        raise ValueError(f"Invalid GitHub username: {username!r}")
    return username


def parse_contributions(document: str) -> dict[date, int]:
    parser = ContributionCalendarParser()
    parser.feed(document)
    parser.close()
    return parser.counts


def fetch_contributions(username: str, attempts: int = 3) -> dict[date, int]:
    username = validate_username(username)
    request = Request(
        f"https://github.com/users/{username}/contributions",
        headers={
            "Accept": "text/html",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "combined-github-contributions/1.0",
        },
    )

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=20) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise ValueError(f"GitHub response for {username} was unexpectedly large")

            counts = parse_contributions(payload.decode("utf-8", errors="replace"))
            if len(counts) < MIN_EXPECTED_DAYS:
                raise ValueError(
                    f"GitHub returned only {len(counts)} calendar days for {username}"
                )
            return counts
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2**attempt)

    raise RuntimeError(f"Unable to load contributions for {username}") from last_error


def merge_contributions(calendars: Iterable[dict[date, int]]) -> dict[date, int]:
    merged: defaultdict[date, int] = defaultdict(int)
    for calendar in calendars:
        for day, count in calendar.items():
            merged[day] += count
    return dict(merged)


def contribution_thresholds(counts: Iterable[int]) -> tuple[int, int, int]:
    positive = sorted(count for count in counts if count > 0)
    if not positive:
        return (1, 1, 1)

    def percentile(fraction: float) -> int:
        index = max(0, math.ceil(len(positive) * fraction) - 1)
        return positive[index]

    return (percentile(0.25), percentile(0.50), percentile(0.75))


def contribution_level(count: int, thresholds: tuple[int, int, int]) -> int:
    if count <= 0:
        return 0
    if count <= thresholds[0]:
        return 1
    if count <= thresholds[1]:
        return 2
    if count <= thresholds[2]:
        return 3
    return 4


def render_svg(counts: dict[date, int], usernames: list[str]) -> str:
    if not counts:
        raise ValueError("Cannot render an empty contribution calendar")

    first_day = min(counts)
    last_day = max(counts)
    start_sunday = first_day - timedelta(days=(first_day.weekday() + 1) % 7)
    weeks = ((last_day - start_sunday).days // 7) + 1

    cell = 10
    gap = 4
    pitch = cell + gap
    left = 30
    top = 22
    width = left + weeks * pitch + 12
    height = top + 7 * pitch + 28
    thresholds = contribution_thresholds(counts.values())

    title = "Combined GitHub contribution activity"
    description = (
        "A visual sum of public daily contribution counts for "
        + " and ".join(usernames)
        + ". This does not modify either GitHub profile."
    )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
            f'aria-labelledby="title description">'
        ),
        f"<title id=\"title\">{html.escape(title)}</title>",
        f"<desc id=\"description\">{html.escape(description)}</desc>",
        "<style>",
        ":root{--fg:#57606a;--l0:#ebedf0;--l1:#9be9a8;--l2:#40c463;--l3:#30a14e;--l4:#216e39}",
        "@media(prefers-color-scheme:dark){:root{--fg:#8b949e;--l0:#161b22;--l1:#0e4429;--l2:#006d32;--l3:#26a641;--l4:#39d353}}",
        "text{fill:var(--fg);font:10px -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}",
        ".day{shape-rendering:geometricPrecision}.level-0{fill:var(--l0)}.level-1{fill:var(--l1)}.level-2{fill:var(--l2)}.level-3{fill:var(--l3)}.level-4{fill:var(--l4)}",
        "</style>",
    ]

    last_label_x = -100
    cursor = date(first_day.year, first_day.month, 1)
    while cursor <= last_day:
        if cursor >= start_sunday:
            week = (cursor - start_sunday).days // 7
            x = left + week * pitch
            if x - last_label_x >= 28:
                lines.append(
                    f'<text x="{x}" y="10">{html.escape(cursor.strftime("%b"))}</text>'
                )
                last_label_x = x
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)

    for label, weekday in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        y = top + weekday * pitch + 9
        lines.append(f'<text x="0" y="{y}">{label}</text>')

    day = start_sunday
    while day <= last_day:
        week = (day - start_sunday).days // 7
        weekday = (day.weekday() + 1) % 7
        x = left + week * pitch
        y = top + weekday * pitch
        count = counts.get(day, 0)
        level = contribution_level(count, thresholds)
        noun = "contribution" if count == 1 else "contributions"
        lines.extend(
            [
                (
                    f'<rect class="day level-{level}" x="{x}" y="{y}" '
                    f'width="{cell}" height="{cell}" rx="2" data-date="{day.isoformat()}" '
                    f'data-count="{count}">'
                ),
                f"<title>{count} combined {noun} on {day.isoformat()}</title>",
                "</rect>",
            ]
        )
        day += timedelta(days=1)

    legend_y = top + 7 * pitch + 15
    legend_x = width - 132
    lines.append(f'<text x="{legend_x}" y="{legend_y + 9}">Less</text>')
    for level in range(5):
        x = legend_x + 28 + level * pitch
        lines.append(
            f'<rect class="day level-{level}" x="{x}" y="{legend_y}" '
            f'width="{cell}" height="{cell}" rx="2" />'
        )
    lines.append(f'<text x="{legend_x + 103}" y="{legend_y + 9}">More</text>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", nargs="+", required=True, help="GitHub usernames")
    parser.add_argument("--output", type=Path, required=True, help="Destination SVG")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    usernames = [validate_username(username) for username in args.users]
    calendars = [fetch_contributions(username) for username in usernames]
    combined = merge_contributions(calendars)
    svg = render_svg(combined, usernames)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    totals = ", ".join(
        f"{username}={sum(calendar.values())}"
        for username, calendar in zip(usernames, calendars, strict=True)
    )
    print(f"Generated {args.output} ({totals}, combined={sum(combined.values())})")


if __name__ == "__main__":
    main()
