#!/usr/bin/env python3
"""Generate animated Linux terminal panels (SVG) for the profile README."""

from __future__ import annotations

import argparse
import html
import textwrap
from dataclasses import dataclass
from pathlib import Path


WIDTH = 900
PADDING = 24
TITLE_BAR = 34
FONT_SIZE = 14
LINE_HEIGHT = 21
CHAR_WIDTH = FONT_SIZE * 0.602
WRAP = 96
TYPE_SPEED = 0.045
LINE_DELAY = 0.05
FONT = "ui-monospace, 'DejaVu Sans Mono', Menlo, Consolas, 'Liberation Mono', monospace"
USER = "sofia@sxfivglz"

COLORS = {
    "bg": "#171421",
    "bar": "#2a2a2e",
    "border": "#3d3846",
    "title": "#c0bfbc",
    "text": "#d0cfcc",
    "dim": "#8f8f96",
    "green": "#8ae234",
    "blue": "#729fcf",
    "yellow": "#fce94f",
    "cyan": "#34e2e2",
    "magenta": "#ad7fa8",
}

Segment = tuple[str, str, bool]
Line = list[Segment]


@dataclass
class Block:
    command: str
    output: list[Line]


@dataclass
class Panel:
    name: str
    blocks: list[Block]


def text_line(text: str, color: str = "text", bold: bool = False) -> Line:
    return [(text, color, bold)]


def wrapped(text: str, color: str = "text", indent: int = 0) -> list[Line]:
    lines = textwrap.wrap(text, WRAP - indent)
    return [text_line(" " * indent + line, color) for line in lines]


def labeled(label: str, text: str, width: int, color: str) -> list[Line]:
    """Render 'label  text' with the text wrapped under its own column."""
    lines = textwrap.wrap(text, WRAP - width)
    result: list[Line] = []
    for index, line in enumerate(lines):
        head = label.ljust(width) if index == 0 else " " * width
        result.append([(head, color, True), (line, "text", False)])
    return result


def prompt(command: str = "") -> Line:
    return [
        (USER, "green", True),
        (":", "text", False),
        ("~", "blue", True),
        ("$ ", "text", False),
        (command, "text", False),
    ]


def render_segments(line: Line) -> str:
    spans = []
    for text, color, bold in line:
        if not text:
            continue
        weight = ' font-weight="bold"' if bold else ""
        spans.append(
            f'<tspan fill="{COLORS[color]}"{weight}>{html.escape(text)}</tspan>'
        )
    return "".join(spans)


def reveal(content: str, begin: float) -> str:
    """Hide content until `begin`; viewers without SVG animation show it at once."""
    return (
        f'<g class="reveal">'
        f'<animate attributeName="opacity" values="0;0" dur="{begin:.2f}s"/>'
        f"{content}</g>"
    )


def typing_steps(chars: int, start: float) -> tuple[str, str, float]:
    """Return values, keyTimes and duration that reveal one character per step."""
    total = start + chars * TYPE_SPEED
    values = ["0"] + [f"{i * CHAR_WIDTH:.1f}" for i in range(chars + 1)]
    times = [0.0] + [(start + i * TYPE_SPEED) / total for i in range(chars + 1)]
    times[-1] = 1.0
    return ";".join(values), ";".join(f"{t:.4f}" for t in times), total


def render_panel(panel: Panel) -> str:
    """Return the SVG markup of one animated terminal window."""
    line_count = sum(1 + len(block.output) for block in panel.blocks) + 1
    height = TITLE_BAR + PADDING * 2 + line_count * LINE_HEIGHT
    prompt_width = len(USER) + 4
    body: list[str] = []
    clips: list[str] = []
    row = 0
    clock = 0.4

    def baseline(index: int) -> float:
        return TITLE_BAR + PADDING + FONT_SIZE + index * LINE_HEIGHT

    for number, block in enumerate(panel.blocks):
        y = baseline(row)
        start_x = PADDING + prompt_width * CHAR_WIDTH
        typing = len(block.command) * TYPE_SPEED
        values, times, total = typing_steps(len(block.command), clock)
        full_width = (len(block.command) + 1) * CHAR_WIDTH
        clips.append(
            f'<clipPath id="{panel.name}-type-{number}">'
            f'<rect class="typed" x="{start_x:.1f}" y="{y - FONT_SIZE:.1f}" '
            f'width="{full_width:.1f}" height="{LINE_HEIGHT}">'
            f'<animate attributeName="width" values="{values}" keyTimes="{times}" '
            f'calcMode="discrete" dur="{total:.2f}s"/></rect>'
            f"</clipPath>"
        )
        prompt_markup = (
            f'<text x="{PADDING}" y="{y:.1f}">{render_segments(prompt())}</text>'
            f'<text x="{start_x:.1f}" y="{y:.1f}" '
            f'clip-path="url(#{panel.name}-type-{number})">'
            f'{render_segments(text_line(block.command))}</text>'
        )
        body.append(reveal(prompt_markup, clock))
        clock += typing + 0.25
        row += 1

        for line in block.output:
            if line:
                markup = f'<text x="{PADDING}" y="{baseline(row):.1f}">'
                markup += f"{render_segments(line)}</text>"
                body.append(reveal(markup, clock))
                clock += LINE_DELAY
            row += 1
        clock += 0.15

    y = baseline(row)
    cursor_x = PADDING + prompt_width * CHAR_WIDTH
    final_prompt = (
        f'<text x="{PADDING}" y="{y:.1f}">{render_segments(prompt())}</text>'
        f'<rect x="{cursor_x:.1f}" y="{y - FONT_SIZE + 2:.1f}" '
        f'width="{CHAR_WIDTH:.1f}" height="{FONT_SIZE + 2}" fill="{COLORS["text"]}">'
        f'<animate attributeName="opacity" values="1;0;1" dur="1.1s" '
        f'repeatCount="indefinite"/></rect>'
    )
    body.append(reveal(final_prompt, clock))

    buttons = []
    for offset, glyph in (
        (24, "M-4,-4 L4,4 M4,-4 L-4,4"),
        (52, "M-4,-4 h8 v8 h-8 Z"),
        (80, "M-4,0 h8"),
    ):
        cx = WIDTH - offset
        buttons.append(
            f'<circle cx="{cx}" cy="17" r="9" fill="#3d3d42"/>'
            f'<path transform="translate({cx},17)" d="{glyph}" '
            f'stroke="{COLORS["title"]}" stroke-width="1.4" fill="none"/>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img">'
        f"<title>{USER}: {panel.name}</title>"
        "<style>"
        f"text{{font-family:{FONT};font-size:{FONT_SIZE}px;white-space:pre}}"
        "@media (prefers-reduced-motion: reduce){"
        ".reveal{opacity:1!important}.typed{width:100%!important}}"
        "</style>"
        f"<defs>{''.join(clips)}</defs>"
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="10" '
        f'fill="{COLORS["bg"]}" stroke="{COLORS["border"]}"/>'
        f'<path d="M0.5,{TITLE_BAR} V10.5 A10,10 0 0 1 10.5,0.5 H{WIDTH - 10.5} '
        f'A10,10 0 0 1 {WIDTH - 0.5},10.5 V{TITLE_BAR} Z" fill="{COLORS["bar"]}"/>'
        f'<text x="{WIDTH / 2}" y="22" text-anchor="middle" fill="{COLORS["title"]}" '
        f'font-weight="bold">{USER}: ~</text>'
        f"{''.join(buttons)}"
        f"{''.join(body)}"
        "</svg>\n"
    )


def build_panels() -> list[Panel]:
    about = Panel(
        "about",
        [
            Block("whoami", [text_line("Sofía Flores", "yellow", True)]),
            Block(
                "cat about.txt",
                [
                    text_line("Software Engineer, AI · Agentic Development", "cyan", True),
                    [],
                    *wrapped(
                        "Software engineer from Mexico with 3+ years of experience "
                        "building web applications, APIs and mobile apps."
                    ),
                    [],
                    *wrapped(
                        "I specialize in agentic development: applications that "
                        "integrate AI agents, chatbots and voice assistants, and "
                        "automations that remove manual work, connected to the systems "
                        "each company already uses. I mainly work with Python / FastAPI "
                        "and TypeScript / Next.js, and I stay involved from technical "
                        "design until the solution runs in production."
                    ),
                    [],
                    [("Location: ", "dim", False), ("Torreón, Coahuila, Mexico", "text", False)],
                ],
            ),
            Block(
                "echo $FOCUS",
                [
                    *wrapped(
                        "Agentic Development · LLM Integrations · MCP Servers · "
                        "WhatsApp Automation · APIs & Integrations · Full Stack "
                        "Development · Production Support",
                        "magenta",
                    ),
                    *wrapped(
                        "I enjoy turning manual, repetitive processes into reliable "
                        "tools that people use every day.",
                        "dim",
                    ),
                ],
            ),
        ],
    )

    stack_rows = [
        ("AI & Agents", "Agentic development, LLMs, AI agents, MCP, tool calling, structured outputs, OpenAI API, Claude API, prompt engineering, text-to-SQL, evals"),
        ("Backend", "Python, FastAPI, Django, PHP, Laravel, REST APIs, Celery"),
        ("Frontend", "TypeScript, JavaScript, Next.js, React, Vue.js"),
        ("Databases", "PostgreSQL, Supabase, Redis, MySQL"),
        ("Mobile", "Android (Java)"),
        ("Infrastructure", "DigitalOcean, AWS S3, Linux, Windows Server, load balancers, DNS and SSL, Docker"),
        ("CI/CD & Testing", "GitHub Actions with self-hosted runners, Git, pytest, Vitest, Playwright"),
        ("Integrations", "WhatsApp Business API, n8n, Twilio, SAT electronic invoicing (CFDI)"),
        ("Dev Workflow", "Claude Code, OpenAI Codex"),
    ]
    stack = Panel(
        "tech-stack",
        [
            Block(
                "cat tech-stack.txt",
                [line for label, text in stack_rows for line in labeled(label, text, 18, "yellow")],
            )
        ],
    )

    projects_data = [
        ("WhatsApp Business Platform", "Python · FastAPI · Redis · Next.js · Supabase",
         "Multi-company platform that connects business phone lines to Meta's WhatsApp API and routes messages to each company's automations. Approved by Meta, with an MCP server so AI agents can query and operate it."),
        ("After-Sales Assistant", "FastAPI · Next.js · Supabase · OpenAI",
         "WhatsApp bot where homeowners report repairs, an admin platform to schedule visits, and an AI agent that classifies reports, validated with test cases before launch."),
        ("Collections & E-Invoicing", "Python · FastAPI · PostgreSQL · OpenAI · n8n",
         "ERP data import, payment reconciliation, account statements, natural-language queries and automated download and validation of SAT electronic invoices."),
        ("Pickleball Tournament App", "REST APIs · relational database",
         "Database architecture, backend and APIs for tournament, player profile and ranking management."),
        ("Field Crew Tracking (team project)", "Laravel",
         "Crew tracking and geolocation for fiber optic and utility pole installation, generating the standardized reports required by internet providers."),
    ]
    project_lines: list[Line] = []
    for name, tech, description in projects_data:
        project_lines.append([("» " + name, "yellow", True)])
        project_lines.append(text_line("  " + tech, "cyan"))
        project_lines.extend(wrapped(description, indent=2))
        project_lines.append([])
    project_lines.extend(
        wrapped(
            "# Most of my work lives in private client repositories under NDA, so "
            "projects are described without client names. I'm happy to walk "
            "through the architecture and decisions in an interview.",
            "dim",
        )
    )
    projects = Panel("featured-projects", [Block("cat featured-projects.txt", project_lines)])

    work_rows = [
        ("Teamwork", "I've worked in development teams since my internship, and today I partner with a consulting team to deliver complete products"),
        ("Clear communication", "I explain the why behind each change and document what I build so others can operate it"),
        ("Problem solving", "I trace production issues end to end, even when the cause is outside our own system"),
        ("Ownership", "I stay with what I build after launch and keep supporting it in production"),
        ("Judgment", "I flag technical, policy and legal risks before building, not after"),
        ("Continuous learning", "I moved from web and mobile development to AI and agentic systems, and keep learning as the field evolves"),
    ]
    how_i_work = Panel(
        "how-i-work",
        [
            Block(
                "cat how-i-work.txt",
                [line for label, text in work_rows for line in labeled(label, text, 22, "green")],
            ),
            Block(
                "ls ~/exploring",
                [text_line("llm-evals  agent-reliability  mcp  cloud-infrastructure  observability", "blue", True)],
            ),
        ],
    )
    return [about, stack, projects, how_i_work]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("assets/terminal"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for panel in build_panels():
        path = args.output_dir / f"{panel.name}.svg"
        path.write_text(render_panel(panel), encoding="utf-8")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
