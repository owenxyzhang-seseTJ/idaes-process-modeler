#!/usr/bin/env python3
"""Plot the bundled demo result CSV files without changing the raw bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 使用无界面后端，保证脚本可在 macOS、Linux 和 HPC 节点运行
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PALETTE = {  # 统一所有面板的语义颜色，便于后续继续扩展图组
    "CO2": "#5DA9A6",  # 用青绿色突出 CO2 目标组分
    "N2": "#D99A8B",  # 用珊瑚色表示 N2 对照组分
    "CH4": "#E6B07E",  # 用橙色表示 CH4 组分
    "A": "#83B6C8",  # 用浅蓝色表示膜反应器反应物 A
    "B": "#8FBC8F",  # 用浅绿色表示膜反应器产物 B
    "H2": "#D48A8A",  # 用砖红色表示 H2 组分
    "diagnostic": "#9AA4B2",  # 用石板灰表示 CSS 和数值诊断
    "ink": "#27323A",  # 统一标题、坐标轴和正文的深色文字
    "muted": "#70777F",  # 用灰色放置次要说明文字
    "grid": "#D9E2E0",  # 使用低对比度网格线帮助读数而不抢主体
    "panel_bg": "#F7FAF8",  # 用极浅底色区分总览中的审计信息面板
}


def configure_style() -> None:
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 9, "axes.labelsize": 10, "axes.titlesize": 10, "legend.fontsize": 8.5, "svg.fonttype": "none", "pdf.fonttype": 42})  # 统一字体、字号和可编辑 SVG/PDF 文本设置


def read_bundle(input_root: Path, name: str) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    bundle = input_root / name
    summary = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
    profiles = pd.read_csv(bundle / "profiles.csv")
    metrics = pd.read_csv(bundle / "metrics.csv")
    return summary, profiles, metrics


def clean_axis(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)  # 隐藏上边框以减轻面板视觉重量
    ax.spines["right"].set_visible(False)  # 隐藏右边框以保持开放式学术坐标轴
    ax.spines["left"].set_color(PALETTE["muted"])  # 将左边框设为低饱和灰色
    ax.spines["bottom"].set_color(PALETTE["muted"])  # 将下边框设为低饱和灰色
    ax.tick_params(axis="both", colors=PALETTE["ink"], length=3, width=0.7)  # 统一刻度颜色和线宽
    ax.grid(axis="y", color=PALETTE["grid"], linewidth=0.6, alpha=0.7)  # 仅在 y 方向添加轻量网格线
    ax.set_axisbelow(True)  # 将网格线放到数据曲线下方


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(-0.12, 1.05, label, transform=ax.transAxes, fontsize=11, fontweight="bold", color=PALETTE["ink"], va="bottom")  # 在每个面板左上方放置小写面板编号


def format_component(component: str) -> str:
    labels = {"CO2": r"CO$_2$", "N2": r"N$_2$", "CH4": r"CH$_4$", "H2": r"H$_2$"}
    return labels.get(component, component)


def save_figure(fig: plt.Figure, output_dir: Path, stem: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / f"{stem}.png", output_dir / f"{stem}.svg", output_dir / f"{stem}.pdf"]
    fig.savefig(paths[0], dpi=220, bbox_inches="tight", facecolor="white")  # 导出高分辨率 PNG 预览并裁掉多余白边
    fig.savefig(paths[1], bbox_inches="tight", facecolor="white")  # 导出保留可编辑文字的 SVG 文件
    fig.savefig(paths[2], bbox_inches="tight", facecolor="white")  # 导出使用 TrueType 字体的 PDF 文件
    plt.close(fig)  # 关闭当前图形，避免批量出图时状态和内存累积
    return [path.name for path in paths]  # 清单只记录相对清单目录的文件名，避免泄露本机绝对路径


def fixed_bed_outlet(profiles: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    outlet_z = profiles["z_m"].max()
    outlet = profiles.loc[profiles["z_m"].eq(outlet_z)].copy()
    concentration = outlet.pivot(index="time_s", columns="component", values="concentration_mol_m3").sort_index()
    total = concentration.sum(axis=1)
    fractions = concentration.div(total.replace(0.0, np.nan), axis=0).fillna(0.0)
    return fractions.index.to_series(index=fractions.index), fractions


def draw_fixed_bed(ax: plt.Axes, summary: dict, profiles: pd.DataFrame, title: str, compact: bool = False) -> None:
    times_s, fractions = fixed_bed_outlet(profiles)
    for component in summary.get("components", fractions.columns.tolist()):
        if component in fractions:
            ax.plot(times_s.to_numpy() / 60.0, fractions[component].to_numpy(), color=PALETTE.get(component, PALETTE["diagnostic"]), linewidth=1.8, label=format_component(component))  # 绘制固定床出口各组分摩尔分数曲线并保持颜色语义一致
    breakthrough = summary.get("breakthrough_time_s")
    if breakthrough is not None:
        ax.axvline(float(breakthrough) / 60.0, color=PALETTE["diagnostic"], linestyle="--", linewidth=1.0, alpha=0.9)  # 标出结果包定义的 CO2 穿透时间
        ax.text(float(breakthrough) / 60.0, 0.06, f"t$_b$ = {float(breakthrough) / 60.0:.1f} min", color=PALETTE["muted"], fontsize=8, rotation=90, va="bottom", ha="right")  # 在穿透线旁标注数值而不遮挡曲线
    if summary.get("backend") == "pyomo_dae_idaes":
        max_fraction = float(fractions.to_numpy().max()) if fractions.size else 0.0
        termination = summary.get("solver", {}).get("termination", "unknown")
        dof = summary.get("degrees_of_freedom_after_discretization", "n/a")
        residual = summary.get("max_constraint_residual", np.nan)
        residual_text = f"{float(residual):.2e}" if np.isfinite(float(residual)) else "n/a"
        note = f"Solve: {termination}\nDOF: {dof}\nMax residual: {residual_text}"
        if max_fraction < 1.0e-8:
            note += "\nOutlet signal < 1e-8 in window"
        ax.text(0.98, 0.55, note, transform=ax.transAxes, ha="right", va="center", fontsize=8, color=PALETTE["muted"])  # 明确标注 IDAES 参考求解证据和短时间窗口内的低出口信号
    ax.set(xlabel="Time (min)", ylabel="Outlet mole fraction", title=title)  # 设置固定床图的英文坐标轴、单位和标题
    ax.set_ylim(0.0, 1.05)  # 保留少量顶部空间以容纳图例和注释
    ax.legend(frameon=False, ncol=2, loc="best")  # 使用无边框图例说明组分颜色
    clean_axis(ax)


def draw_psa(ax: plt.Axes, summary: dict, metrics: pd.DataFrame, title: str, compact: bool = False) -> None:
    cycles = metrics["cycle"].to_numpy(dtype=float)
    ax.plot(cycles, metrics["purity"].to_numpy(dtype=float) * 100.0, color=PALETTE["CO2"], marker="o", markersize=3.5, linewidth=1.8, label="Purity")  # 绘制 PSA 产品纯度随循环变化的曲线
    ax.plot(cycles, metrics["recovery"].to_numpy(dtype=float) * 100.0, color=PALETTE["N2"], marker="o", markersize=3.5, linewidth=1.8, label="Recovery")  # 绘制 PSA 回收率随循环变化的曲线
    ax.set(xlabel="Cycle", ylabel="Performance (%)", title=title)  # 设置 PSA 性能图的英文坐标轴和百分比单位
    ax.set_ylim(0.0, 100.0)  # 固定性能百分比范围以便直观解读
    final_css = metrics["css_state_delta"].dropna()
    css_text = f"CSS Δ = {float(final_css.iloc[-1]):.2e}" if not final_css.empty else "CSS Δ = n/a"
    ax.text(0.98, 0.08, css_text, transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=PALETTE["muted"])  # 在面板底部标注最终 CSS 状态差
    ax.legend(frameon=False, loc="best")  # 使用无边框图例区分纯度和回收率
    clean_axis(ax)


def draw_membrane(ax: plt.Axes, summary: dict, profiles: pd.DataFrame, title: str, compact: bool = False) -> None:
    target = summary.get("target_component", summary.get("components", ["CO2"])[0])
    for component in summary.get("components", []):
        subset = profiles.loc[profiles["component"].eq(component)].sort_values("z_m")
        color = PALETTE.get(component, PALETTE["diagnostic"])
        ax.plot(subset["z_m"], subset["retentate_mole_fraction"], color=color, linewidth=1.8, label=f"Retentate {format_component(component)}")  # 绘制膜截留侧各组分摩尔分数
        if component == target:
            ax.plot(subset["z_m"], subset["permeate_mole_fraction"], color=color, linestyle="--", linewidth=1.4, label=f"Permeate {format_component(component)}")  # 用虚线补充目标组分渗透侧组成
    ax.set(xlabel="Membrane coordinate (m)", ylabel="Mole fraction", title=title)  # 设置膜分离图的空间坐标、摩尔分数和标题
    ax.set_ylim(0.0, 1.0)  # 将组成范围限制在物理可解释的 0 到 1 之间
    purity = summary.get("purity")
    recovery = summary.get("recovery")
    stage_cut = summary.get("stage_cut")
    ax.text(0.98, 0.08, f"Purity {float(purity):.3f}\nRecovery {float(recovery):.3f}\nStage cut {float(stage_cut):.3f}", transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=PALETTE["muted"])  # 在膜图中标出结果包的三个核心指标
    ax.legend(frameon=False, ncol=2, loc="best")  # 使用紧凑图例区分截留侧和渗透侧
    clean_axis(ax)


def draw_membrane_reactor(ax: plt.Axes, summary: dict, profiles: pd.DataFrame, title: str) -> None:
    for component in summary.get("components", []):
        subset = profiles.loc[profiles["component"].eq(component)].sort_values("z_m")
        ax.plot(subset["z_m"], subset["reaction_side_flow_mol_s"], color=PALETTE.get(component, PALETTE["diagnostic"]), linewidth=1.8, label=f"Reaction side {format_component(component)}")  # 绘制膜反应器反应侧各组分摩尔流率
    target = summary.get("membrane_component", "H2")
    target_subset = profiles.loc[profiles["component"].eq(target)].sort_values("z_m")
    ax.plot(target_subset["z_m"], target_subset["permeate_flow_mol_s"], color=PALETTE.get(target, PALETTE["diagnostic"]), linestyle="--", linewidth=1.4, label=f"Permeated {format_component(target)}")  # 用虚线显示目标组分累计渗透流率
    ax.set(xlabel="Axial coordinate (m)", ylabel="Molar flow (mol s$^{-1}$)", title=title)  # 设置膜反应器图的空间坐标、流率单位和标题
    conversion = float(summary.get("conversion", np.nan))
    permeated = float(summary.get("permeated_target_mol_s", np.nan))
    ax.text(0.98, 0.08, f"Conversion {conversion:.3f}\nPermeated {format_component(target)} {permeated:.4f} mol s$^{{-1}}$", transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=PALETTE["muted"])  # 标注膜反应器的转化率和渗透量
    ax.legend(frameon=False, ncol=2, loc="best")  # 使用紧凑图例区分反应侧和渗透侧
    clean_axis(ax)


def draw_snapshot(ax: plt.Axes, summaries: dict[str, dict]) -> None:
    ax.set_facecolor(PALETTE["panel_bg"])  # 用浅色底突出审计信息而不改变数据面板背景
    ax.axis("off")  # 关闭坐标轴以便将面板用于结果卡片而非伪造比较坐标
    psa = summaries["psa"]
    membrane = summaries["membrane"]
    reactor = summaries["membrane_reactor"]
    idaes_ref = summaries["idaes_fixed_bed"]
    lines = [
        "Headline outputs",
        f"PSA: purity {psa['purity']:.3f} · recovery {psa['recovery']:.3f}",
        f"Membrane: purity {membrane['purity']:.3f} · recovery {membrane['recovery']:.3f}",
        f"Membrane reactor: conversion {reactor['conversion']:.3f}",
        f"IDAES reference: {idaes_ref['solver']['termination']}",
        "",
        "Scope",
        "Reduced-order results are scenario outputs.",
        "IDAES reference uses ideal-gas, constant P/T equations.",
        "No experimental validation is claimed.",
    ]
    ax.text(0.06, 0.92, "\n".join(lines), transform=ax.transAxes, va="top", ha="left", color=PALETTE["ink"], fontsize=9.2, linespacing=1.45)  # 将关键数值和证据边界排成可审计的结果卡片


def plot_psa_detail(summary: dict, metrics: pd.DataFrame, output_dir: Path) -> list[str]:
    cycles = metrics["cycle"].to_numpy(dtype=float)
    css = metrics["css_state_delta"].to_numpy(dtype=float)
    fig, axes = plt.subplots(2, 1, figsize=(6.4, 5.8), sharex=True, constrained_layout=True)  # 创建 PSA 细节图的上下双面板
    draw_psa(axes[0], summary, metrics, "PSA performance", compact=False)
    axes[1].semilogy(cycles[1:], np.maximum(css[1:], 1.0e-16), color=PALETTE["diagnostic"], marker="o", markersize=3.5, linewidth=1.7)  # 用对数纵轴展示 CSS 状态差的收敛过程
    axes[1].set(xlabel="Cycle", ylabel="CSS state delta", title="Cyclic steady-state convergence")  # 设置 CSS 子图的坐标轴、单位和标题
    clean_axis(axes[1])
    return save_figure(fig, output_dir, "psa_performance_detail")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "demo_results")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "demo_results" / "figures")
    args = parser.parse_args(argv)
    configure_style()
    summaries = {}
    bundles = {}
    for name in ("fixed_bed", "psa", "membrane", "membrane_reactor", "idaes_fixed_bed"):
        summary, profiles, metrics = read_bundle(args.input_dir, name)
        summaries[name] = summary
        bundles[name] = (profiles, metrics)
    fixed_summary, (fixed_profiles, _) = summaries["fixed_bed"], bundles["fixed_bed"]
    psa_summary, (_, psa_metrics) = summaries["psa"], bundles["psa"]
    membrane_summary, (membrane_profiles, _) = summaries["membrane"], bundles["membrane"]
    reactor_summary, (reactor_profiles, _) = summaries["membrane_reactor"], bundles["membrane_reactor"]
    idaes_summary, (idaes_profiles, _) = summaries["idaes_fixed_bed"], bundles["idaes_fixed_bed"]
    generated = {}
    fig, axes = plt.subplots(2, 3, figsize=(12.6, 8.0), constrained_layout=True)  # 创建五个结果面板和一个证据边界面板
    draw_fixed_bed(axes[0, 0], fixed_summary, fixed_profiles, "Fixed-bed adsorption", compact=True)
    draw_psa(axes[0, 1], psa_summary, psa_metrics, "PSA cycle", compact=True)
    draw_membrane(axes[0, 2], membrane_summary, membrane_profiles, "Membrane separation", compact=True)
    draw_membrane_reactor(axes[1, 0], reactor_summary, reactor_profiles, "Membrane reactor")
    draw_fixed_bed(axes[1, 1], idaes_summary, idaes_profiles, "IDAES/Pyomo.DAE reference", compact=True)
    draw_snapshot(axes[1, 2], summaries)
    for ax, label in zip(axes.flat, ("a", "b", "c", "d", "e", "f")):
        add_panel_label(ax, label)
    fig.suptitle("IDAES Process Modeler demo results", fontsize=14, fontweight="bold", color=PALETTE["ink"])  # 设置总览图主标题并保持证据边界清晰
    generated["demo_results_overview"] = save_figure(fig, args.output_dir, "demo_results_overview")
    single_figures = {}
    fig, ax = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)  # 创建 fixed-bed 单独展示图
    draw_fixed_bed(ax, fixed_summary, fixed_profiles, "Fixed-bed adsorption breakthrough")
    single_figures["fixed_bed"] = save_figure(fig, args.output_dir, "fixed_bed_breakthrough")
    single_figures["psa"] = plot_psa_detail(psa_summary, psa_metrics, args.output_dir)
    fig, ax = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)  # 创建 membrane 单独展示图
    draw_membrane(ax, membrane_summary, membrane_profiles, "CO$_2$/CH$_4$ membrane separation")
    single_figures["membrane"] = save_figure(fig, args.output_dir, "membrane_profiles_detail")
    fig, ax = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)  # 创建 membrane-reactor 单独展示图
    draw_membrane_reactor(ax, reactor_summary, reactor_profiles, "H$_2$-selective membrane reactor")
    single_figures["membrane_reactor"] = save_figure(fig, args.output_dir, "membrane_reactor_detail")
    fig, ax = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)  # 创建 IDAES reference 单独展示图
    draw_fixed_bed(ax, idaes_summary, idaes_profiles, "IDAES/Pyomo.DAE fixed-bed reference")
    single_figures["idaes_fixed_bed"] = save_figure(fig, args.output_dir, "idaes_reference_breakthrough")
    generated["single_figures"] = single_figures
    (args.output_dir / "plot_manifest.json").write_text(json.dumps(generated, indent=2), encoding="utf-8")
    print(json.dumps(generated, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
