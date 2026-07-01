#!/usr/bin/env python3
import argparse
import json
import sys
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint

from agent.parser import parse_requirement
from agent.planner import build_plan
from agent.loop import run_agent
from agent.schemas import FinalResponse

console = Console()


def display_response(resp: FinalResponse):
    req = resp.interpreted_requirement

    console.print(Panel(
        f"[bold cyan]Suproc Agent — Final Response[/bold cyan]\n"
        f"Validation: {resp.validation_status} (attempt {resp.validation_attempts}/3)",
        expand=False,
    ))

    console.rule("[bold]Interpreted Requirement")
    console.print(f"[b]Objective:[/b] {req.objective}")
    console.print(f"[b]Entity Type:[/b] {req.entity_type}")
    console.print(f"[b]Requested Results:[/b] {req.requested_results}")

    console.rule("[bold]Execution Plan")
    for i, step in enumerate(resp.plan_followed.steps, 1):
        console.print(f"  {i}. {step}")

    console.rule("[bold]Recommendations")
    if not resp.recommendations:
        console.print("[red]No valid recommendations found.[/red]")
    for rec in resp.recommendations:
        e = rec.entity
        s = rec.score
        console.print(Panel(
            f"[b]#{rec.rank} — {e.name}[/b] ({e.id})\n"
            f"Location: {e.location}, {e.state}\n"
            f"Certifications: {e.certifications}\n"
            f"Capacity: {e.capacity_units} units | Delivery: {e.delivery_days} days\n"
            f"Availability: {e.availability} | Rating: {e.rating}/5\n\n"
            f"[b]Why Suitable:[/b] {rec.why_suitable}\n\n"
            f"[b]Score TOTAL: {s.total}/100[/b]\n",
            title=f"Match #{rec.rank}",
            border_style="green" if s.total >= 60 else "yellow",
        ))

    if resp.draft_outreach_messages:
        console.rule("[bold]Draft Outreach Messages")
        for msg in resp.draft_outreach_messages:
            console.print(Panel(
                f"[b]To:[/b] {msg.recipient_name} ({msg.recipient_id})\n"
                f"[b]Subject:[/b] {msg.subject}\n\n"
                f"{msg.body}",
                title="Draft Message",
                border_style="blue",
            ))

    if resp.warnings:
        console.rule("[bold yellow]Warnings")
        for w in resp.warnings:
            console.print(f"  [yellow]⚠[/yellow] {w}")

    console.rule("[bold red]Human Approval Required")
    console.print(Panel(
        f"[b]Recommended Next Action:[/b]\n{resp.recommended_next_action}\n\n"
        f"[bold red]Status: {resp.approval_status}[/bold red]\n",
        border_style="red",
    ))


def main():
    parser = argparse.ArgumentParser(description="Suproc Local Agent")
    parser.add_argument("--request", type=str, help="Business requirement (if not provided, interactive mode)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted display")
    args = parser.parse_args()

    if args.request:
        user_input = args.request
    else:
        console.print("[bold cyan]Suproc Local Agentic Search System[/bold cyan]")
        console.print("Enter your business requirement (or 'quit' to exit):\n")
        user_input = input("> ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            sys.exit(0)

    with console.status("[bold green]Parsing requirement..."):
        req = parse_requirement(user_input)

    with console.status("[bold green]Building execution plan..."):
        plan = build_plan(req)

    with console.status("[bold green]Running agent (search → filter → score → validate)..."):
        response = run_agent(req, plan)

    if args.json:
        print(response.model_dump_json(indent=2))
    else:
        display_response(response)


if __name__ == "__main__":
    main()
