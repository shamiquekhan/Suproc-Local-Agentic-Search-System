#!/usr/bin/env python3
import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent.parser import parse_requirement
from agent.planner import build_plan
from agent.loop import run_agent
from agent.schemas import FinalResponse

console = Console()


def display_response(resp: FinalResponse):
    req = resp.interpreted_requirement
    hc = req.hard_constraints
    pr = req.preferences

    console.print(Panel(
        f"[bold cyan]Suproc Agent - Final Response[/bold cyan]\n"
        f"Validation: {resp.validation_status} (attempt {resp.validation_attempts}/3)",
        expand=False,
    ))

    # --- Interpreted Requirement ---
    console.rule("[bold]Interpreted Requirement")
    console.print(f"  [b]Objective:[/b]         {req.objective}")
    console.print(f"  [b]Entity Type:[/b]       {req.entity_type}")
    console.print(f"  [b]Requested Results:[/b] {req.requested_results}")

    console.print("\n  [b]Hard Constraints:[/b]")
    console.print(f"    Locations:       {hc.locations or 'any'}")
    console.print(f"    Certifications:  {hc.certifications or 'none required'}")
    console.print(f"    Min Capacity:    {hc.minimum_capacity or 'not specified'}")
    console.print(f"    Max Delivery:    {f'{hc.maximum_delivery_days} days' if hc.maximum_delivery_days else 'not specified'}")
    console.print(f"    Availability:    {hc.availability or 'any'}")

    console.print("\n  [b]Preferences:[/b]")
    console.print(f"    Sustainable Materials: {pr.sustainable_materials}")
    console.print(f"    Startup Friendly:      {pr.startup_friendly}")
    if pr.min_rating:
        console.print(f"    Min Rating:            {pr.min_rating}")
    if pr.category:
        console.print(f"    Category:              {pr.category}")

    # --- Execution Plan ---
    console.rule("[bold]Execution Plan")
    for i, step in enumerate(resp.plan_followed.steps, 1):
        console.print(f"  {i}. {step}")

    # --- Recommendations ---
    console.rule("[bold]Recommendations")
    if not resp.recommendations:
        console.print("[red]No valid recommendations found.[/red]")

    for rec in resp.recommendations:
        e = rec.entity
        s = rec.score

        # Score breakdown table
        score_table = Table(box=None, show_header=True, header_style="bold")
        score_table.add_column("Dimension", style="dim")
        score_table.add_column("Score", justify="right")
        score_table.add_column("Max", justify="right")
        score_table.add_column("Evidence")
        score_table.add_row("Product Relevance",   f"{s.product_relevance}",   "30", s.evidence.get("relevance", ""))
        score_table.add_row("Location Suitability", f"{s.location_suitability}", "20", s.evidence.get("location", ""))
        score_table.add_row("Constraint Compliance", f"{s.constraint_compliance}", "25", s.evidence.get("constraints", ""))
        score_table.add_row("Availability/Capacity", f"{s.availability_capacity}", "15", s.evidence.get("availability", ""))
        score_table.add_row("Reputation",           f"{s.reputation}",          "10", s.evidence.get("reputation", ""))

        missing = "\n    ".join(rec.missing_information) if rec.missing_information else "none"
        risks   = "\n    ".join(rec.risks) if rec.risks else "none"

        body = (
            f"[b]#{rec.rank}: {e.name}[/b] ({e.id})\n"
            f"Location:       {e.location}, {e.state}\n"
            f"Certifications: {', '.join(e.certifications) if e.certifications else 'none on file'}\n"
            f"Capacity:       {e.capacity_units or 'unknown'} units  |  "
            f"Delivery: {e.delivery_days or 'unknown'} days\n"
            f"Availability:   {e.availability}  |  Rating: {e.rating or 'n/a'}/5\n\n"
            f"[b]Why Suitable:[/b] {rec.why_suitable}\n\n"
            f"[b]Score: {s.total}/100[/b]\n"
        )

        console.print(Panel(body, title=f"Match #{rec.rank}",
                            border_style="green" if s.total >= 60 else "yellow"))
        console.print(score_table)

        if rec.missing_information:
            console.print(f"  [yellow]Missing info:[/yellow]")
            for item in rec.missing_information:
                console.print(f"    - {item}")

        if rec.risks:
            console.print(f"  [red]Risks / notes:[/red]")
            for item in rec.risks:
                console.print(f"    - {item}")

        console.print()

    # --- Validation failures (if any) ---
    if resp.validation_failures:
        console.rule("[bold yellow]Validation Failures")
        for f in resp.validation_failures:
            console.print(f"  [{f.entity_id}] {f.failure_type}: {f.detail}")

    # --- Draft Outreach ---
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

    # --- Warnings ---
    if resp.warnings:
        console.rule("[bold yellow]Warnings")
        for w in resp.warnings:
            console.print(f"  [yellow]![/yellow] {w}")

    # --- Approval gate ---
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

    with console.status("[bold green]Running agent (search -> filter -> score -> validate)..."):
        response = run_agent(req, plan)

    if args.json:
        print(response.model_dump_json(indent=2))
    else:
        display_response(response)


if __name__ == "__main__":
    main()
