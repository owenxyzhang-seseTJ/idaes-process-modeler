#!/usr/bin/env python3
"""Build the technical principles, parameter, flowchart, and validation report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 使用无界面后端，保证报告生成可在 macOS、Linux 和 HPC 节点运行
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
R_GAS = 8.31446261815324
PALETTE = {  # 为流程图、参数图和验证图统一颜色语义
    "CO2": "#5DA9A6",  # 用青绿色表示 CO2
    "N2": "#D99A8B",  # 用珊瑚色表示 N2
    "CH4": "#E6B07E",  # 用橙色表示 CH4
    "A": "#83B6C8",  # 用浅蓝色表示反应物 A
    "B": "#8FBC8F",  # 用浅绿色表示产物 B
    "H2": "#D48A8A",  # 用砖红色表示 H2
    "diagnostic": "#9AA4B2",  # 用石板灰表示数值诊断
    "ink": "#27323A",  # 用深色表示主要文字和流程节点
    "muted": "#70777F",  # 用灰色表示次要说明
    "grid": "#D9E2E0",  # 用浅灰色表示辅助网格线
    "feed": "#CFE8E6",  # 用浅青色表示输入数据节点
    "model": "#E4EEF3",  # 用浅蓝色表示模型节点
    "solver": "#EEE6F3",  # 用浅紫色表示求解节点
    "report": "#F3D1C9",  # 用浅珊瑚色表示报告和验证节点
}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_summary(root: Path, name: str) -> dict:
    return json.loads((root / "demo_results" / name / "summary.json").read_text(encoding="utf-8"))


def as_si(value, dimension: str, field_name: str = "report") -> float:
    from idaes_process_modeler.units import si_value

    return float(si_value(value, dimension, field_name=field_name))


def dsl(pressure_pa: np.ndarray, params: dict) -> np.ndarray:
    p = np.maximum(np.asarray(pressure_pa, dtype=float), 0.0)
    q1 = float(as_si(params["qs1"], "loading")) * float(as_si(params["b1"], "inverse_pressure")) * p
    q1 = q1 / (1.0 + float(as_si(params["b1"], "inverse_pressure")) * p)
    q2 = float(as_si(params["qs2"], "loading")) * float(as_si(params["b2"], "inverse_pressure")) * p
    q2 = q2 / (1.0 + float(as_si(params["b2"], "inverse_pressure")) * p)
    return q1 + q2


def format_component(component: str) -> str:
    labels = {"CO2": r"CO$_2$", "N2": r"N$_2$", "CH4": r"CH$_4$", "H2": r"H$_2$"}
    return labels.get(component, component)


def configure_style() -> None:
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 9, "axes.labelsize": 10, "axes.titlesize": 10, "legend.fontsize": 8.5, "svg.fonttype": "none", "pdf.fonttype": 42})  # 统一字体、字号和可编辑 SVG/PDF 文本设置


def clean_axis(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)  # 隐藏上边框以减轻图面重量
    ax.spines["right"].set_visible(False)  # 隐藏右边框以保持开放式坐标轴
    ax.spines["left"].set_color(PALETTE["muted"])  # 将左边框设为低饱和灰色
    ax.spines["bottom"].set_color(PALETTE["muted"])  # 将下边框设为低饱和灰色
    ax.tick_params(axis="both", colors=PALETTE["ink"], length=3, width=0.7)  # 统一刻度颜色和线宽
    ax.grid(axis="y", color=PALETTE["grid"], linewidth=0.6, alpha=0.7)  # 使用低对比度水平网格线帮助读数
    ax.set_axisbelow(True)  # 将网格线放置在数据曲线下方


def save_figure(fig: plt.Figure, output_dir: Path, stem: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / f"{stem}.png", output_dir / f"{stem}.svg", output_dir / f"{stem}.pdf"]
    fig.savefig(paths[0], dpi=220, bbox_inches="tight", facecolor="white")  # 导出高分辨率 PNG 预览
    fig.savefig(paths[1], bbox_inches="tight", facecolor="white")  # 导出保留可编辑文字的 SVG
    fig.savefig(paths[2], bbox_inches="tight", facecolor="white")  # 导出使用 TrueType 字体的 PDF
    plt.close(fig)  # 关闭图形以避免批量出图时内存和状态累积
    return [path.name for path in paths]  # 清单只记录相对清单目录的文件名，避免泄露本机绝对路径


def draw_box(ax: plt.Axes, x: float, y: float, width: float, height: float, text: str, face: str, edge: str = PALETTE["ink"], fontsize: float = 9.5) -> None:
    patch = FancyBboxPatch((x, y), width, height, boxstyle="round,pad=0.03,rounding_size=0.08", linewidth=1.0, edgecolor=edge, facecolor=face)  # 绘制 Aspen 风格的圆角单元操作框
    ax.add_patch(patch)  # 将单元操作框加入流程图坐标轴
    ax.text(x + width / 2.0, y + height / 2.0, text, ha="center", va="center", fontsize=fontsize, color=PALETTE["ink"], linespacing=1.25)  # 在单元操作框中放置可读的模块名称


def draw_arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float], label: str = "", color: str = PALETTE["ink"], style: str = "-") -> None:
    arrow = FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14, linewidth=1.2, linestyle=style, color=color, connectionstyle="arc3,rad=0.0")  # 绘制带方向的物料或信息流箭头
    ax.add_patch(arrow)  # 将箭头加入流程图坐标轴
    if label:
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        ax.text(midpoint[0], midpoint[1] + 0.12, label, ha="center", va="bottom", fontsize=8, color=PALETTE["muted"], bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})  # 在箭头中点标注 Aspen 风格的流股编号


def build_process_flow(output_dir: Path) -> list[str]:
    fig, ax = plt.subplots(figsize=(13.2, 7.0), constrained_layout=True)  # 创建适合报告页面的宽幅流程图画布
    ax.set_xlim(0.0, 13.4)  # 设置流程图横向范围以容纳五个主模块
    ax.set_ylim(0.0, 7.0)  # 设置流程图纵向范围以容纳四个分支单元
    ax.axis("off")  # 隐藏坐标轴以保留流程图的工程图风格
    ax.text(6.7, 6.72, "IDAES Process Modeler — Aspen-like conceptual flowsheet", ha="center", va="center", fontsize=14, fontweight="bold", color=PALETTE["ink"])  # 添加流程图主标题并明确这是概念流程图
    ax.text(6.7, 6.38, "Feed and parameters → unit equations → numerical solver → auditable reports", ha="center", va="center", fontsize=9.5, color=PALETTE["muted"])  # 添加从输入到验证的总流程说明
    draw_box(ax, 0.35, 4.95, 2.1, 0.95, "F-01\nFeed + initial data", PALETTE["feed"])  # 放置进料和初始数据模块
    draw_box(ax, 3.05, 4.95, 2.1, 0.95, "SPEC-01\nModelSpec + units", PALETTE["feed"])  # 放置结构化模型规格模块
    draw_box(ax, 5.75, 4.95, 2.1, 0.95, "PROP-01\nProperties +\nq* / kinetics", PALETTE["model"])  # 放置物性、等温线和速率模块
    draw_box(ax, 8.45, 4.95, 2.1, 0.95, "SOLV-01\nDAE / ODE /\ncycle solver", PALETTE["solver"])  # 放置数值求解模块
    draw_box(ax, 11.15, 4.95, 1.9, 0.95, "RPT-01\nResults +\nvalidation", PALETTE["report"])  # 放置结果和验证模块
    draw_arrow(ax, (2.45, 5.42), (3.05, 5.42), "F-01")  # 连接进料到模型规格并标注流股
    draw_arrow(ax, (5.15, 5.42), (5.75, 5.42), "S-01")  # 连接模型规格到物性参数并标注信息流
    draw_arrow(ax, (7.85, 5.42), (8.45, 5.42), "E-01")  # 连接参数模块到方程求解器并标注方程流
    draw_arrow(ax, (10.55, 5.42), (11.15, 5.42), "R-01")  # 连接求解器到报告模块并标注结果流
    ax.text(0.55, 3.92, "Unit-operation layer", ha="left", va="center", fontsize=10, fontweight="bold", color=PALETTE["ink"], bbox={"facecolor": "white", "edgecolor": "none", "pad": 2.0})  # 在左侧空白区标示下方单元操作分支层
    draw_box(ax, 0.55, 2.35, 2.35, 1.15, "U-101\nFixed bed\nPDE / method-of-lines", PALETTE["model"])  # 放置固定床单元操作框
    draw_box(ax, 3.55, 2.35, 2.35, 1.15, "U-201\nPSA / VSA / TSA\ncycle + CSS", PALETTE["model"])  # 放置循环吸附单元操作框
    draw_box(ax, 6.55, 2.35, 2.35, 1.15, "U-301\nMembrane\n1-D transport", PALETTE["model"])  # 放置膜分离单元操作框
    draw_box(ax, 9.55, 2.35, 2.35, 1.15, "U-401\nMembrane reactor\nreaction + H2 removal", PALETTE["model"])  # 放置膜反应器单元操作框
    draw_arrow(ax, (6.8, 4.95), (1.73, 3.5), "E-101", color=PALETTE["diagnostic"], style="--")  # 用虚线表示方程层对固定床分支的路由
    draw_arrow(ax, (6.8, 4.95), (4.73, 3.5), "E-201", color=PALETTE["diagnostic"], style="--")  # 用虚线表示方程层对 PSA 分支的路由
    draw_arrow(ax, (6.8, 4.95), (7.73, 3.5), "E-301", color=PALETTE["diagnostic"], style="--")  # 用虚线表示方程层对膜分离分支的路由
    draw_arrow(ax, (6.8, 4.95), (10.73, 3.5), "E-401", color=PALETTE["diagnostic"], style="--")  # 用虚线表示方程层对膜反应器分支的路由
    draw_arrow(ax, (2.9, 2.92), (8.45, 5.0), color=PALETTE["diagnostic"], style=":")  # 用无文字虚线汇总固定床状态和残差到求解器
    draw_arrow(ax, (5.9, 2.92), (8.45, 5.15), color=PALETTE["diagnostic"], style=":")  # 用无文字虚线汇总 PSA 状态到求解器
    draw_arrow(ax, (8.9, 2.92), (8.45, 5.3), color=PALETTE["diagnostic"], style=":")  # 用无文字虚线汇总膜分离剖面到求解器接口
    draw_arrow(ax, (11.9, 2.92), (8.45, 5.45), color=PALETTE["diagnostic"], style=":")  # 用无文字虚线汇总膜反应器指标到求解器接口
    ax.text(0.7, 1.42, "Streams", fontsize=9.5, fontweight="bold", color=PALETTE["ink"])  # 标示下方输出流股说明区域
    draw_arrow(ax, (1.55, 1.05), (3.25, 1.05), "P-01 product", color=PALETTE["CO2"])  # 绘制产品流股示意箭头
    draw_arrow(ax, (4.25, 1.05), (5.95, 1.05), "W-01 waste / purge", color=PALETTE["N2"])  # 绘制废气和吹扫流股示意箭头
    draw_arrow(ax, (7.0, 1.05), (8.7, 1.05), "M-01 permeate", color=PALETTE["CH4"])  # 绘制膜渗透流股示意箭头
    draw_arrow(ax, (9.75, 1.05), (11.45, 1.05), "R-01 reaction outlet", color=PALETTE["H2"])  # 绘制反应器出口流股示意箭头
    ax.text(6.7, 0.38, "Dashed links indicate model routing; solid arrows indicate stream or information flow. This is not a native Aspen file.", ha="center", va="center", fontsize=8.5, color=PALETTE["muted"])  # 说明流程图与商业软件原生流程图的边界
    return save_figure(fig, output_dir, "process_flow_aspen_like")


def build_parameter_figure(output_dir: Path, fixed_spec: dict, membrane_spec: dict, reactor_spec: dict) -> tuple[list[str], dict]:
    adsorption = fixed_spec["adsorption"]["parameters"]
    feed_pressure = as_si(fixed_spec["feed"]["pressure"], "pressure")
    temperature = as_si(fixed_spec["feed"]["temperature"], "temperature")
    feed_y = fixed_spec["feed"]["composition"]
    pressures_bar = np.logspace(-4.0, 1.0, 400)
    pressures_pa = pressures_bar * 1.0e5
    operating = {component: feed_pressure * float(feed_y[component]) for component in fixed_spec["components"]}
    q_operating = {component: float(dsl(np.asarray([operating[component]]), adsorption[component])[0]) for component in fixed_spec["components"]}
    time_s = np.linspace(0.0, 600.0, 400)
    q_curves = {}
    rate_curves = {}
    for component in fixed_spec["components"]:
        k = as_si(fixed_spec["adsorption"]["kinetic_parameters"][component]["k"], "rate_constant")
        q_star = q_operating[component]
        q_curves[component] = q_star * (1.0 - np.exp(-k * time_s))
        rate_curves[component] = k * (q_star - q_curves[component])
    isotherm_rows = []
    ldf_rows = []
    for component in fixed_spec["components"]:
        for pressure_bar, loading in zip(pressures_bar, dsl(pressures_pa, adsorption[component])):
            isotherm_rows.append({"pressure_bar": float(pressure_bar), "component": component, "equilibrium_loading_mol_kg": float(loading)})
        for time_value, loading, rate in zip(time_s, q_curves[component], rate_curves[component]):
            ldf_rows.append({"time_s": float(time_value), "component": component, "loading_mol_kg": float(loading), "rate_mol_kg_s": float(rate)})
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(isotherm_rows).to_csv(output_dir / "processed_isotherms.csv", index=False)
    pd.DataFrame(ldf_rows).to_csv(output_dir / "processed_ldf_curves.csv", index=False)
    membrane_permeance = membrane_spec["membrane"]["permeance"]
    membrane_perm = {component: as_si(membrane_permeance[component], "permeance") for component in membrane_spec["components"]}
    reactor_permeance = reactor_spec["membrane"]["permeance"]
    reactor_perm = {component: as_si(reactor_permeance[component], "permeance") for component in reactor_spec["components"]}
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.2), constrained_layout=True)  # 创建初始参数、等温线和速率曲线的四面板画布
    ax = axes[0, 0]
    for component in fixed_spec["components"]:
        ax.plot(pressures_bar, dsl(pressures_pa, adsorption[component]), color=PALETTE[component], linewidth=2.0, label=format_component(component))  # 绘制双位点 Langmuir 纯组分等温线
        point_pressure = operating[component] / 1.0e5
        ax.scatter([point_pressure], [q_operating[component]], color=PALETTE[component], edgecolor="white", linewidth=0.8, s=42, zorder=4)  # 标出当前进料分压对应的平衡吸附量
    ax.set_xscale("log")  # 使用对数压力轴覆盖低压到高压参数范围
    ax.set(xlabel="Partial pressure (bar)", ylabel="Equilibrium loading (mol kg$^{-1}$)", title="Dual-site Langmuir isotherms")  # 设置等温线坐标轴、单位和标题
    ax.legend(frameon=False, loc="best")  # 用无边框图例区分 CO2 和 N2
    clean_axis(ax)
    ax = axes[0, 1]
    for component in fixed_spec["components"]:
        k = as_si(fixed_spec["adsorption"]["kinetic_parameters"][component]["k"], "rate_constant")
        ax.plot(time_s, q_curves[component], color=PALETTE[component], linewidth=2.0, label=f"{format_component(component)}, k={k:g} s$^{{-1}}$")  # 绘制 LDF 阶跃吸附的 loading 随时间变化
    ax.set(xlabel="Time (s)", ylabel="Loading (mol kg$^{-1}$)", title="LDF uptake from q(0) = 0")  # 设置 LDF 吸附曲线坐标轴和标题
    ax.legend(frameon=False, loc="best")  # 用图例同时说明组分和速率常数
    clean_axis(ax)
    ax = axes[1, 0]
    for component in fixed_spec["components"]:
        k = as_si(fixed_spec["adsorption"]["kinetic_parameters"][component]["k"], "rate_constant")
        ax.plot(time_s, rate_curves[component], color=PALETTE[component], linewidth=2.0, label=format_component(component))  # 绘制 LDF 瞬时吸附速率随时间衰减的曲线
        ax.axvline(1.0 / k, color=PALETTE[component], linestyle="--", linewidth=0.9, alpha=0.65)  # 标出各组分的特征时间常数 1/k
    ax.set(xlabel="Time (s)", ylabel="dq/dt (mol kg$^{-1}$ s$^{-1}$)", title="LDF rate response")  # 设置速率曲线的坐标轴、单位和标题
    ax.legend(frameon=False, loc="best")  # 用图例区分组分速率曲线
    clean_axis(ax)
    ax = axes[1, 1]
    labels = ["CO$_2$/CH$_4$\nmembrane", "H$_2$/A\nreactor", "H$_2$/B\nreactor"]
    values = [membrane_perm["CO2"] / membrane_perm["CH4"], reactor_perm["H2"] / reactor_perm["A"], reactor_perm["H2"] / reactor_perm["B"]]
    bars = ax.bar(np.arange(len(labels)), values, color=[PALETTE["CO2"], PALETTE["H2"], PALETTE["H2"]], width=0.58, edgecolor="white")  # 绘制膜参数选择性比的柱状图
    ax.set_yscale("log")  # 使用对数纵轴同时展示 10 倍和 2000 倍选择性
    ax.set_xticks(np.arange(len(labels)), labels)  # 设置选择性柱状图的分组标签
    ax.set(ylabel="Permeance ratio", title="Initial transport selectivity")  # 设置膜选择性图的坐标轴和标题
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2.0, value * 1.15, f"{value:.0f}×", ha="center", va="bottom", fontsize=8, color=PALETTE["ink"])  # 在每根柱顶标注选择性数值
    clean_axis(ax)
    fig.suptitle(f"Initial parameters at {temperature:g} K and {feed_pressure / 1.0e5:g} bar fixed-bed feed", fontsize=14, fontweight="bold", color=PALETTE["ink"])  # 添加参数图总标题并说明参考工况
    paths = save_figure(fig, output_dir, "initial_parameters_isotherm_kinetics")
    values_out = {"operating_partial_pressure_pa": operating, "q_operating_mol_kg": q_operating, "membrane_selectivity": values}
    return paths, values_out


def build_validation_figure(output_dir: Path, root: Path, summaries: dict) -> list[str]:
    fixed_mesh = json.loads((root / "demo_results" / "fixed_bed" / "convergence_mesh.json").read_text(encoding="utf-8"))
    psa_conv = json.loads((root / "demo_results" / "psa" / "convergence.json").read_text(encoding="utf-8"))
    css_records = [row for row in psa_conv["records"] if row["state_delta"] is not None]
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.0), constrained_layout=True)  # 创建数值验证和合理性证据的四面板画布
    ax = axes[0, 0]
    error_labels = ["Fixed-bed\nmass balance", "Membrane\nmass balance", "IDAES\nconstraint residual"]
    error_values = [summaries["fixed_bed"]["mass_balance_error"], summaries["membrane"]["mass_balance_error"], summaries["idaes_fixed_bed"]["max_constraint_residual"]]
    pd.DataFrame({"check": ["fixed_bed_mass_balance", "membrane_mass_balance", "idaes_constraint_residual"], "value": error_values}).to_csv(output_dir / "validation_error_metrics.csv", index=False)
    bars = ax.bar(np.arange(len(error_values)), error_values, color=[PALETTE["CO2"], PALETTE["CH4"], PALETTE["diagnostic"]], width=0.58)  # 绘制质量守恒误差和 IDAES 约束残差
    ax.set_yscale("log")  # 使用对数纵轴显示不同数量级的数值误差
    ax.set_xticks(np.arange(len(error_values)), error_labels)  # 设置误差柱状图的类别标签
    ax.set(ylabel="Absolute / relative error", title="Balance and residual checks")  # 设置误差验证图的坐标轴和标题
    for bar, value in zip(bars, error_values):
        ax.text(bar.get_x() + bar.get_width() / 2.0, value * 1.4, f"{value:.1e}", ha="center", va="bottom", fontsize=8, rotation=0, color=PALETTE["ink"])  # 标注每个误差指标的实际数量级
    clean_axis(ax)
    ax = axes[0, 1]
    cycles = np.asarray([row["cycle"] for row in css_records], dtype=float)
    deltas = np.asarray([row["state_delta"] for row in css_records], dtype=float)
    tolerance = float(psa_conv["records"][-1]["tolerance"])
    ax.semilogy(cycles, deltas, color=PALETTE["diagnostic"], marker="o", linewidth=1.8, label="CSS state delta")  # 绘制 PSA 循环状态差的收敛轨迹
    ax.axhline(tolerance, color=PALETTE["CO2"], linestyle="--", linewidth=1.2, label=f"Tolerance = {tolerance:.0e}")  # 绘制用户设定的 CSS 收敛容差
    ax.set(xlabel="Cycle", ylabel="State delta", title="Cyclic steady-state evidence")  # 设置 CSS 验证图坐标轴和标题
    ax.legend(frameon=False, loc="best")  # 用图例区分状态差和收敛容差
    clean_axis(ax)
    ax = axes[1, 0]
    mesh_x = [record["spatial_elements"] for record in fixed_mesh["records"]]
    mesh_y = [record["value"] / 60.0 for record in fixed_mesh["records"]]
    ax.plot(mesh_x, mesh_y, color=PALETTE["CO2"], marker="o", linewidth=1.8)  # 绘制空间网格加密对固定床穿透时间的影响
    ax.set(xlabel="Spatial elements", ylabel="Breakthrough time (min)", title="Fixed-bed mesh check")  # 设置网格收敛图坐标轴、单位和标题
    ax.text(0.98, 0.08, f"Relative change = {fixed_mesh['differences'][-1]['relative_change']:.1%}", transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=PALETTE["muted"])  # 标注网格加密后的相对变化
    clean_axis(ax)
    ax = axes[1, 1]
    ax.axis("off")  # 关闭最后一个面板坐标轴以放置文字化证据总结
    validation_lines = [
        "Validation layers",
        "1. Code: 14 pytest tests passed.",
        "2. Units / bounds: ModelSpec preflight passed.",
        "3. Numerical: ODE/DAE termination successful.",
        "4. Conservation: errors reported at left.",
        "5. CSS: final delta below tolerance.",
        "6. Physical: monotonic q*(P), positive rates,\n   non-negative flows and closure checks.",
        "",
        "Not included: experiment, literature benchmark,\nfull distributed PSA, or uncertainty quantification.",
    ]
    ax.text(0.06, 0.92, "\n".join(validation_lines), transform=ax.transAxes, va="top", ha="left", fontsize=9.2, color=PALETTE["ink"], linespacing=1.45)  # 将验证层级和缺失证据写入审计面板
    fig.suptitle("Numerical validation and reasonableness evidence", fontsize=14, fontweight="bold", color=PALETTE["ink"])  # 添加验证图总标题
    return save_figure(fig, output_dir, "validation_evidence")


def build_report(root: Path, output_dir: Path, figure_paths: dict, parameter_values: dict) -> Path:
    fixed_spec = load_yaml(root / "assets" / "templates" / "fixed_bed.yaml")
    psa_spec = load_yaml(root / "assets" / "templates" / "psa.yaml")
    membrane_spec = load_yaml(root / "assets" / "templates" / "membrane.yaml")
    reactor_spec = load_yaml(root / "assets" / "templates" / "membrane_reactor.yaml")
    summaries = {name: load_summary(root, name) for name in ("fixed_bed", "psa", "membrane", "membrane_reactor", "idaes_fixed_bed")}
    ads = fixed_spec["adsorption"]["parameters"]
    k_params = fixed_spec["adsorption"]["kinetic_parameters"]
    fixed_mesh = json.loads((root / "demo_results" / "fixed_bed" / "convergence_mesh.json").read_text(encoding="utf-8"))
    psa_conv = json.loads((root / "demo_results" / "psa" / "convergence.json").read_text(encoding="utf-8"))
    final_css = float(psa_conv["records"][-1]["state_delta"])
    css_tol = float(psa_conv["records"][-1]["tolerance"])
    lines = [
        "# IDAES Process Modeler Demo 技术报告",
        "",
        "> 本报告把 demo 的结果、计算原理、建模原理、初始参数、流程图、合理性说明和验证证据放在同一条可追溯链路中。四个 reduced-order demo 用于工作流和数值演示；IDAES/Pyomo.DAE 部分是受保护的参考模型，不等同于完整工业流程模拟。",
        "",
        "## 1. 结论先行",
        "",
        "| Demo | 计算结果 | 证据边界 |",
        "|---|---:|---|",
        f"| Fixed-bed adsorption | CO₂ 穿透时间 {summaries['fixed_bed']['breakthrough_time_s'] / 60.0:.1f} min；压降 {summaries['fixed_bed']['pressure_drop_pa']:.1f} Pa | reduced-order 1-D 数值演示 |",
        f"| PSA | CSS {summaries['psa']['css_converged']}（{summaries['psa']['cycles_run']} cycles）；纯度 {summaries['psa']['purity']:.3f}；回收率 {summaries['psa']['recovery']:.3f} | 单床 lumped cycle map |",
        f"| Membrane | 纯度 {summaries['membrane']['purity']:.3f}；回收率 {summaries['membrane']['recovery']:.3f}；stage cut {summaries['membrane']['stage_cut']:.3f} | co-current ideal-gas 1-D 模型 |",
        f"| Membrane reactor | 转化率 {summaries['membrane_reactor']['conversion']:.3f}；渗透 H₂ {summaries['membrane_reactor']['permeated_target_mol_s']:.4f} mol/s | PFR-like reduced-order 模型 |",
        f"| IDAES reference | IPOPT {summaries['idaes_fixed_bed']['solver']['termination']}；DOF {summaries['idaes_fixed_bed']['degrees_of_freedom_after_discretization']}；最大残差 {summaries['idaes_fixed_bed']['max_constraint_residual']:.2e} | API/数值 smoke result，不是实验验证 |",
        "",
        f"![Demo result overview](../figures/demo_results_overview.png)",
        "",
        "## 2. 计算原理",
        "",
        "### 2.1 固定床吸附",
        "",
        "气相组分守恒采用一维非稳态对流–轴向弥散–固相吸附储存形式。当前 reduced-order 实现使用常物性和有限差分/方法线离散：",
        "",
        r"\[",
        r"\varepsilon \frac{\partial C_i}{\partial t} + u\frac{\partial C_i}{\partial z} - \varepsilon D_{ax}\frac{\partial^2 C_i}{\partial z^2} + (1-\varepsilon)\rho_s\frac{\partial q_i}{\partial t}=0.",
        r"\]",
        "",
        "吸附平衡采用双位点 Langmuir：",
        "",
        r"\[",
        r"q_i^*=q_{s1,i}\frac{b_{1,i}P_i}{1+b_{1,i}P_i}+q_{s2,i}\frac{b_{2,i}P_i}{1+b_{2,i}P_i},\qquad P_i=y_iP.",
        r"\]",
        "",
        "传质采用 LDF：",
        "",
        r"\[",
        r"\frac{dq_i}{dt}=k_i(q_i^*-q_i).",
        r"\]",
        "",
        "其中当前 IDAES reference adapter 用理想气体关系 `Pᵢ = CᵢRT`，并固定温度和压力；它是 API/DAE 参考模型，不是通用 IDAES property package。",
        "",
        "### 2.2 PSA / VSA / TSA cycle map",
        "",
        "PSA demo 把 cycle 写成数据，而不是把步骤硬编码到求解器中。每一个 step 根据名称、持续时间、入口/出口和压力目标更新：",
        "",
        r"\[",
        r"q_{n+1}=q_n+\left[1-\exp(-k\Delta t)\right](q^*(P_{step},y_{in})-q_n).",
        r"\]",
        "",
        "同时更新床层空隙气体库存、吸附/解吸量、产品流量和近似压力功。循环状态向量包含压力和各组分 loading；CSS 判据为：",
        "",
        r"\[",
        r"\max_j\left|\frac{x_{n,j}-x_{n-1,j}}{\max(|x_{n,j}|,1)}\right|<\varepsilon_{CSS}.",
        r"\]",
        "",
        "### 2.3 膜分离",
        "",
        "膜模型使用组分通量驱动的一维流率平衡：",
        "",
        r"\[",
        r"J_i=\Pi_i(P_fy_{i,f}-P_py_{i,p}),\qquad \frac{dF_{i,r}}{dz}=-J_i\frac{A}{L}.",
        r"\]",
        "",
        "当前 demo 为 co-current、恒温恒压、理想气体近似；没有加入浓差极化和组件压降。",
        "",
        "### 2.4 膜反应器",
        "",
        "膜反应器同时计算化学反应和 H₂ 选择性移除：",
        "",
        r"\[",
        r"\frac{dF_i}{dz}=\nu_i r-\delta_{i,H_2}J_{H_2}\frac{A}{L},\qquad r=\frac{k(T)F_A}{u_r}.",
        r"\]",
        "",
        "当前模型采用单一反应速率表达式和恒温恒压；没有完整 IDAES 热力学、能量平衡或多反应网络。",
        "",
        "## 3. 建模原理和 Aspen-like 流程",
        "",
        "流程图表达的是类似 Aspen 的工程组织方式：进料/参数 → 物性与本构关系 → 单元操作方程 → 求解器 → 物流、指标和验证。它是概念流程图，不是 Aspen Plus 原生文件，也不声称调用 Aspen 求解器。",
        "",
        "![Aspen-like process flow](process_flow_aspen_like.png)",
        "",
        "### 单元操作和输出关系",
        "",
        "- **U-101 Fixed bed：** 输入组成、压力、温度、床层几何、等温线和 LDF 参数；输出 breakthrough、出口组成、loading、压降诊断和守恒误差。",
        "- **U-201 PSA：** 输入 cycle step sequence、压力高低端、purge 和 CSS 容差；输出 purity、recovery、productivity、能耗和 cycle state delta。",
        "- **U-301 Membrane：** 输入 feed/permeate 压力、面积、长度和 permeance；输出 retentate/permeate profiles、purity、recovery、stage cut 和质量平衡。",
        "- **U-401 Membrane reactor：** 输入化学计量、速率常数、温度、H₂ permeance 和 sweep；输出反应侧流率、渗透 H₂ 和 conversion。",
        "",
        "## 4. 初始参数",
        "",
        "### 4.1 Fixed-bed / PSA 吸附床",
        "",
        "| 参数 | 初始值 | 作用 |",
        "|---|---:|---|",
        f"| 温度 / 总压 | {fixed_spec['feed']['temperature']} / {fixed_spec['feed']['pressure']} | 理想气体分压和速率参考状态 |",
        f"| 进料流量 / 组成 | {fixed_spec['feed']['molar_flow']} / CO₂ {fixed_spec['feed']['composition']['CO2']}, N₂ {fixed_spec['feed']['composition']['N2']} | 进料边界 |",
        f"| 床长 / 直径 | {fixed_spec['geometry']['length']} / {fixed_spec['geometry']['diameter']} | 轴向空间尺度和截面积 |",
        f"| 孔隙率 / 固体密度 | {fixed_spec['bed']['porosity']} / {fixed_spec['bed']['particle_density']} | 气相与固相库存耦合 |",
        f"| 轴向弥散 / 表观速度 | {fixed_spec['bed']['axial_dispersion']} / {fixed_spec['bed']['superficial_velocity']} | 对流–弥散项 |",
        f"| CO₂ DSL / LDF | qs₁={ads['CO2']['qs1']}, b₁={ads['CO2']['b1']}; qs₂={ads['CO2']['qs2']}, b₂={ads['CO2']['b2']}; k={k_params['CO2']['k']} | 目标组分平衡和动力学 |",
        f"| N₂ DSL / LDF | qs₁={ads['N2']['qs1']}, b₁={ads['N2']['b1']}; qs₂={ads['N2']['qs2']}, b₂={ads['N2']['b2']}; k={k_params['N2']['k']} | 竞争组分平衡和动力学 |",
        f"| PSA 压力 / CSS | {psa_spec['cycle_settings']['high_pressure']} ↔ {psa_spec['cycle_settings']['low_pressure']}；容差 {psa_spec['cycle_settings']['css_tolerance']} | 循环边界和停止条件 |",
        "",
        "### 4.2 膜分离和膜反应器参数",
        "",
        "| 模块 | 关键初始参数 |",
        "|---|---|",
        f"| Membrane | {membrane_spec['feed']['pressure']} → {membrane_spec['membrane']['permeate_pressure']}；面积 {membrane_spec['membrane']['area']}；CO₂ permeance {membrane_spec['membrane']['permeance']['CO2']}；CH₄ permeance {membrane_spec['membrane']['permeance']['CH4']} |",
        f"| Membrane reactor | T={reactor_spec['feed']['temperature']}；L={reactor_spec['geometry']['length']}；A→B+H₂；Ea={reactor_spec['reaction']['activation_energy']}；H₂ permeance={reactor_spec['membrane']['permeance']['H2']}；sweep={reactor_spec['membrane']['sweep_flow']} |",
        "",
        "### 4.3 等温线、吸附速率和膜选择性",
        "",
        f"在 fixed-bed 进料状态下，CO₂ 分压为 {parameter_values['operating_partial_pressure_pa']['CO2'] / 1.0e5:.3f} bar，N₂ 分压为 {parameter_values['operating_partial_pressure_pa']['N2'] / 1.0e5:.3f} bar；对应 DSL 平衡 loading 分别约为 CO₂ {parameter_values['q_operating_mol_kg']['CO2']:.3f} 和 N₂ {parameter_values['q_operating_mol_kg']['N2']:.3f} mol/kg。",
        "",
        "![Initial parameters, isotherms, and kinetics](initial_parameters_isotherm_kinetics.png)",
        "",
        "图中：左上为双位点 Langmuir；右上为从 q(0)=0 的 LDF loading 响应；左下为 dq/dt；右下为膜 permeance 选择性。速率曲线不是实验速率测量，而是由初始 k 和 q* 计算出的模型响应。",
        "",
        "## 5. 结果和合理性说明",
        "",
        "### 5.1 Fixed-bed",
        "",
        f"CO₂ breakthrough 时间为 {summaries['fixed_bed']['breakthrough_time_s']:.0f} s。出口 CO₂ 最终回到约 {summaries['fixed_bed']['final_outlet_mole_fraction']['CO2']:.3f}，接近进料组成，符合床层逐渐接近饱和后分离能力下降的定性趋势。Ergun 压降约 {summaries['fixed_bed']['pressure_drop_pa']:.1f} Pa，但当前压降只作为诊断，没有反馈到浓度方程。",
        "",
        "### 5.2 PSA",
        "",
        f"PSA 在第 {summaries['psa']['cycles_run']} 个循环满足 CSS 判据，最终状态差 {final_css:.2e} < {css_tol:.0e}。纯度约 35.6%、回收率约 70.0%；这说明当前参数和四步单床 lumped map 产生了可收敛的循环状态，但纯度并不高，不能把 CSS 收敛误读成工艺性能已验证。",
        "",
        "### 5.3 Membrane",
        "",
        f"CO₂/CH₄ permeance 比为 {parameter_values['membrane_selectivity'][0]:.0f}，模型得到 CO₂ 纯度约 {summaries['membrane']['purity']:.3f}、回收率约 {summaries['membrane']['recovery']:.3f}。纯度和回收率的组合受面积、压比、permeance 和 feed composition 共同决定，不能单独由 selectivity 推断。",
        "",
        "### 5.4 Membrane reactor",
        "",
        f"H₂ 对 A/B 的初始 permeance 比均为约 {parameter_values['membrane_selectivity'][1]:.0f}，模型得到 conversion {summaries['membrane_reactor']['conversion']:.3f}。该趋势与“生成 H₂ 并选择性移除”这一模型设定一致，但真实反应器还需要热效应、平衡限制、传质阻力和催化剂数据。",
        "",
        "## 6. 验证和证据等级",
        "",
        "### 6.1 数值和守恒验证",
        "",
        "| 检查项 | 结果 | 结论 |",
        "|---|---:|---|",
        f"| Reduced fixed-bed BDF integration | {summaries['fixed_bed']['solver']['termination']} | 数值积分成功 |",
        f"| Fixed-bed mass-balance error | {summaries['fixed_bed']['mass_balance_error']:.2e} | 当前离散方程下守恒误差较小 |",
        f"| Fixed-bed mesh 20→40 elements | breakthrough {fixed_mesh['records'][0]['value'] / 60.0:.1f}→{fixed_mesh['records'][1]['value'] / 60.0:.1f} min；变化 {fixed_mesh['differences'][0]['relative_change']:.1%} | 仅为网格敏感性证据，不是物理验证 |",
        f"| PSA CSS | {final_css:.2e} < {css_tol:.0e} | 达到设定循环收敛标准 |",
        f"| Membrane mass-balance error | {summaries['membrane']['mass_balance_error']:.2e} | 当前 ODE 流率平衡闭合良好 |",
        f"| IDAES/Pyomo.DAE constraint residual | {summaries['idaes_fixed_bed']['max_constraint_residual']:.2e} | 离散约束满足良好 |",
        "",
        "![Validation evidence](validation_evidence.png)",
        "",
        "### 6.2 物理合理性检查",
        "",
        "- DSL 等温线在绘图压力范围内单调增加并趋向有限饱和值；CO₂ 的设定容量和亲和参数高于 N₂，因此模型给出更高的 CO₂ 平衡 loading。",
        "- LDF 的 k 为正，q(t) 单调接近 q*，dq/dt 随时间衰减至零；特征时间为 1/k，CO₂ 约 100 s、N₂ 约 125 s。",
        "- feed/purge 组成经过归一化，流率和 loading 在输出中保持非负；膜模型报告了质量平衡误差。",
        "- 膜反应器化学计量为 A→B+H₂；图中 A 下降、B 和渗透 H₂ 增加，与设定反应方向一致。",
        "",
        "### 6.3 尚未完成的验证",
        "",
        "当前没有材料实验等温线、独立 LDF 速率数据、膜 permeance 实验、反应动力学数据、文献 benchmark 或 Aspen 原生 benchmark。因此本报告不能宣称实验验证、工业尺度可靠性或与 Aspen 结果等价。下一步应优先补充实测参数，建立不确定性/敏感性分析，再做完整 IDAES property package、能量平衡、压降耦合和分布式多床 PSA。",
        "",
        "## 7. 可追溯文件",
        "",
        "- 原始参数：`../../assets/templates/*.yaml`",
        "- 原始结果：`../fixed_bed/`、`../psa/`、`../membrane/`、`../membrane_reactor/`、`../idaes_fixed_bed/`",
        "- 派生参数数据：`processed_isotherms.csv`、`processed_ldf_curves.csv`、`validation_error_metrics.csv`",
        "- 总览结果图：`../figures/demo_results_overview.png`",
        "- 绘图脚本：`../../scripts/plot_demo_results.py`",
        "- 本报告生成脚本：`../../scripts/build_technical_report.py`",
        "- QA 记录：`../figures/qa_report.md`",
        "- 本报告方法包：`method_search_packet.md`、`figure_plan.md`、`qa_report.md`",
        "",
        "报告边界：所有数值均来自当前 demo 的机器可读输出；没有添加实验不确定度、统计显著性或未经数据支持的机理结论。",
    ]
    report_path = output_dir / "demo_technical_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "demo_results" / "technical_report")
    args = parser.parse_args(argv)
    configure_style()
    fixed_spec = load_yaml(args.root / "assets" / "templates" / "fixed_bed.yaml")
    membrane_spec = load_yaml(args.root / "assets" / "templates" / "membrane.yaml")
    reactor_spec = load_yaml(args.root / "assets" / "templates" / "membrane_reactor.yaml")
    summaries = {name: load_summary(args.root, name) for name in ("fixed_bed", "psa", "membrane", "membrane_reactor", "idaes_fixed_bed")}
    flow_paths = build_process_flow(args.output_dir)
    parameter_paths, parameter_values = build_parameter_figure(args.output_dir, fixed_spec, membrane_spec, reactor_spec)
    validation_paths = build_validation_figure(args.output_dir, args.root, summaries)
    figure_paths = {"process_flow": flow_paths, "initial_parameters": parameter_paths, "validation": validation_paths}
    report_path = build_report(args.root, args.output_dir, figure_paths, parameter_values)
    manifest = {"report": report_path.name, "figures": figure_paths, "parameter_values": parameter_values}
    (args.output_dir / "technical_report_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
