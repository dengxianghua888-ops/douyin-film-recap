from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .config import load_config
from .doctor import run_doctor
from .pipeline import FilmRecapPipeline, StageBlocked
from .state import STAGES

app = typer.Typer(
    name="douyin-film-recap",
    help="将电影或电视剧自动制作成抖音影视解说成片。",
    no_args_is_help=True,
)
console = Console()


@app.command()
def doctor(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="YAML 配置文件"),
    ] = Path("config.yaml"),
) -> None:
    """检查 FFmpeg、模型、ASR、TTS 与发布边界。"""
    try:
        resolved = config.expanduser().resolve()
        app_config = load_config(resolved)
        checks = run_doctor(app_config, resolved)
    except Exception as exc:
        console.print(f"[bold red]配置加载失败：[/bold red] {exc}")
        raise typer.Exit(code=2) from exc
    table = Table(title="Douyin Film Recap Doctor")
    table.add_column("检查项")
    table.add_column("状态")
    table.add_column("详情")
    for check in checks:
        style = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}.get(
            check.status, "white"
        )
        table.add_row(check.name, f"[{style}]{check.status}[/{style}]", check.detail)
    console.print(table)
    if any(check.critical for check in checks):
        raise typer.Exit(code=1)


@app.command("run")
def run_pipeline(
    input_path: Annotated[Path, typer.Argument(help="视频文件或素材目录")],
    work_dir: Annotated[
        Path,
        typer.Option("--work-dir", "-w", help="项目工作目录"),
    ],
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="YAML 配置文件"),
    ] = Path("config.yaml"),
    until: Annotated[
        str | None,
        typer.Option("--until", help="运行到指定阶段后停止"),
    ] = None,
    from_stage: Annotated[
        str | None,
        typer.Option("--from-stage", help="从指定阶段强制重算"),
    ] = None,
) -> None:
    """执行完整或分阶段的影视解说生产管线。"""
    if until and until not in STAGES:
        console.print(f"[red]未知阶段：{until}[/red]\n可用阶段：{', '.join(STAGES)}")
        raise typer.Exit(code=2)
    if from_stage and from_stage not in STAGES:
        console.print(
            f"[red]未知阶段：{from_stage}[/red]\n可用阶段：{', '.join(STAGES)}"
        )
        raise typer.Exit(code=2)
    try:
        app_config = load_config(config)
        pipeline = FilmRecapPipeline(
            input_path=input_path,
            work_dir=work_dir,
            config=app_config,
            on_update=lambda message: console.print(f"[cyan]{message}[/cyan]"),
        )
        result = pipeline.run(until=until, from_stage=from_stage)
        console.print(f"\n[bold green]完成[/bold green]：{result}")
    except StageBlocked as exc:
        console.print(f"\n[bold red]{exc.stage} 被质量门禁阻断[/bold red]")
        for finding in exc.report.findings:
            marker = "BLOCK" if finding.blocking else finding.severity.upper()
            console.print(f"- [{marker}] {finding.rule_id}: {finding.message}")
        raise typer.Exit(code=3) from exc
    except Exception as exc:
        console.print(f"\n[bold red]执行失败：[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def status(
    work_dir: Annotated[Path, typer.Argument(help="项目工作目录")],
) -> None:
    """查看断点续跑状态。"""
    state_path = work_dir.expanduser().resolve() / "state.json"
    if not state_path.exists():
        console.print(f"[red]未找到状态文件：{state_path}[/red]")
        raise typer.Exit(code=1)
    data = json.loads(state_path.read_text(encoding="utf-8"))
    table = Table(title=data.get("project_name", "Film Recap Project"))
    table.add_column("阶段")
    table.add_column("状态")
    table.add_column("产物")
    table.add_column("错误")
    for stage in STAGES:
        record = data.get("stages", {}).get(stage, {})
        status_value = record.get("status", "pending")
        style = {
            "passed": "green",
            "running": "cyan",
            "failed": "red",
            "skipped": "yellow",
            "pending": "dim",
        }.get(status_value, "white")
        error = record.get("error") or {}
        table.add_row(
            stage,
            f"[{style}]{status_value}[/{style}]",
            str(record.get("artifact") or ""),
            str(error.get("message") or ""),
        )
    console.print(table)


@app.command("stages")
def list_stages() -> None:
    """列出可断点运行的阶段。"""
    for index, stage in enumerate(STAGES, start=1):
        console.print(f"{index:02d}. {stage}")
