#!/usr/bin/env python3
"""Reproduce a sourced NaCl-equivalent seawater RO demo, figures and report."""
import argparse
import importlib.metadata
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

from idaes_process_modeler.engine import run_model
from idaes_process_modeler.models.seawater_ro import parameters, calibrate, simulate, solve_pyomo
from idaes_process_modeler.reporting import write_result_bundle
from idaes_process_modeler.spec import load_spec

ROOT = Path(__file__).resolve().parents[1]


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)+'\n',encoding='utf-8')


def export(fig, path):
    for ext in ('png','svg','pdf'):
        fig.savefig(path.with_suffix('.'+ext), dpi=200, bbox_inches='tight')  # 保留清晰预览与可编辑矢量图
    plt.close(fig)  # 释放绘图窗口与内存


def plot_results(out, frame, sweep, calframe, sensitivity):
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})  # 统一字号并保留可编辑文字
    fig, axes = plt.subplots(2,3,figsize=(13,7.3),layout='constrained')  # 六面板展示空间变化与压力影响
    a=axes.ravel()
    a[0].plot(frame.area_m2,frame.bulk_g_L,label='Bulk',color='#287C8E')  # 深色为主体溶液盐度
    a[0].plot(frame.area_m2,frame.surface_g_L,label='Membrane surface',color='#D38437')  # 橙色显示浓差极化
    a[0].set(xlabel='Cumulative membrane area (m²)',ylabel='NaCl (g/L)',title='a  Concentration polarization')  # 标注空间坐标与量纲
    a[0].legend(frameon=False)  # 区分主体与膜表面
    a[1].plot(frame.area_m2,frame.flux_L_m2_h,color='#287C8E')  # 显示沿膜面积变化的产水通量
    a[1].set(xlabel='Cumulative membrane area (m²)',ylabel='Water flux (L m⁻² h⁻¹)',title='b  Axial water flux')  # 给出通量单位
    a[2].plot(frame.area_m2,frame.local_permeate_mg_L,color='#D38437')  # 局部产水盐度不是混合产水盐度
    a[2].set(xlabel='Cumulative membrane area (m²)',ylabel='Local permeate NaCl (mg/L)',title='c  Local permeate quality')  # 强调局部浓度定义
    a[3].plot(sweep.pressure_bar,100*sweep.recovery,color='#287C8E')  # 压力扫描计算回收率
    a[3].set(xlabel='Feed pressure (bar)',ylabel='Recovery (%)',title='d  Pressure sweep prediction')  # 说明为预测工况
    a[4].plot(sweep.pressure_bar,sweep.permeate_mg_L,color='#D38437')  # 显示压力对混合产水盐度影响
    a[4].set(xlabel='Feed pressure (bar)',ylabel='Mixed permeate NaCl (mg/L)',title='e  Product salinity')  # 区分混合值和局部值
    a[5].plot(sweep.pressure_bar,sweep.sec_no_erd_kWh_m3,label='No energy recovery',color='#D38437')  # 无能量回收的高压泵耗电
    a[5].plot(sweep.pressure_bar,sweep.sec_pressure_exchanger_kWh_m3,label='Pressure exchanger, assumed',color='#287C8E')  # 理想化压力交换器场景
    a[5].set(xlabel='Feed pressure (bar)',ylabel='RO pressure-work SEC (kWh/m³)',title='f  Hydraulic energy scenarios')  # 不包含预处理和其他辅机能耗
    a[5].legend(frameon=False,fontsize=8)  # 避免图例遮挡曲线
    fig.suptitle('NaCl-equivalent seawater RO | 6 × 37 m² | 25°C | scenario predictions',fontsize=15)  # 总标题清楚标记模型结果
    export(fig,out/'figures/ro_performance')
    fig, ax = plt.subplots(figsize=(8,3.8),layout='constrained')  # 标定与预测信息分开作图
    ax.plot(calframe.area_m2,calframe.flux_L_m2_h,color='#287C8E',label='Fitted axial prediction')  # 单元件标定后轴向曲线
    ax.axhline(28.4/24/37*1000,color='#D38437',ls='--',label='Manufacturer nominal area-average flux')  # 标称值为面积平均值而非局部实测
    ax.set(xlabel='Membrane area (m²)',ylabel='Water flux (L m⁻² h⁻¹)',title='55 bar calibration | 28.4 m³/day, 99.8% rejection')  # 展示公开数据对应条件
    ax.legend(frameon=False)  # 说明标称数据与拟合曲线区别
    export(fig,out/'figures/calibration')
    fig, ax = plt.subplots(figsize=(8,4.2),layout='constrained')  # 独立展示假设敏感性
    ax.barh(sensitivity.case,sensitivity.permeate_m3_day,color='#287C8E')  # 横条方便阅读工况名称
    ax.set(xlabel='Predicted permeate (m³/day)',title='One-at-a-time sensitivity | A and B held fixed')  # 明示扫描不重新拟合膜参数
    export(fig,out/'figures/sensitivity')
    fig, ax = plt.subplots(figsize=(12,4.1),layout='constrained')  # 流程图独立导出以便报告复用
    ax.set(xlim=(0,12),ylim=(0,4))  # 定义流程图绘制坐标
    ax.axis('off')  # 隐藏与流程无关的坐标轴
    boxes=[(0.2,2.2,1.6,'F-101\nNaCl feed\n32 g/L'),(2.7,2.2,1.6,'P-101\nHP pump\n60 bar'),(5.2,2.2,2.1,'RO-101\n6 elements\n222 m²'),(9.1,2.8,2.4,'W-101\nMixed permeate'),(8.3,.4,2.5,'ERD-101\nPressure exchanger\noptional energy credit')]
    for x,y,w,label in boxes:
        ax.add_patch(FancyBboxPatch((x,y),w,1,boxstyle='round,pad=0.06',facecolor='#E6F2F3',edgecolor='#287C8E'))  # 统一设备框样式
        ax.text(x+w/2,y+.5,label,ha='center',va='center',fontsize=10)  # 设备位号和操作条件置于框内
    for start,end in [((1.9,2.7),(2.6,2.7)),((4.4,2.7),(5.1,2.7)),((7.4,3),(9,3.3)),((7.4,2.5),(8.2,.95)),((10.9,.9),(11.9,.9))]:
        ax.annotate('',xy=end,xytext=start,arrowprops={'arrowstyle':'->','color':'#287C8E','lw':1.8})  # 实线箭头表示物料流向
    ax.annotate('',xy=(3.5,2.1),xytext=(8.2,.65),arrowprops={'arrowstyle':'->','color':'#D38437','ls':'--','connectionstyle':'angle,angleA=180,angleB=-90,rad=10'})  # 虚线表示回收压力功而非详细管路
    ax.text(6,.2,'Dashed: recovered hydraulic work; conceptual flowsheet',ha='center',fontsize=9,color='#9A5F29')  # 标明示意图精度边界
    ax.text(11.55,1.2,'Brine',ha='center',fontsize=9)  # 标注浓水出口
    ax.set_title('Steady, isothermal reverse osmosis | Aspen-style conceptual flowsheet',fontsize=13)  # 明确稳态等温流程
    export(fig,out/'figures/flowsheet')


def report(out, s, A, B, checks, sensitivity, standard_train):
    table='\n'.join(f'| {r.case} | {r.permeate_m3_day:.3f} | {100*r.recovery:.2f} | {r.permeate_mg_L:.2f} |' for r in sensitivity.itertuples())
    text=rf'''# 海水反渗透脱盐 / Seawater reverse osmosis

## 1. 实际数据及证据 / Source data and evidence

本案例采用 DuPont FilmTec SW30HRLE-400 官方产品数据表（45-D00967-en，Rev. 8，January 2026，第 1 页）。数据为厂商标准测试下的标称性能；没有公开逐点原始实验或误差棒。访问日期：2026-09-13。

Manufacturer nominal values, not a raw experimental dataset. A and B are calibrated to the two performance targets; this is not independent experimental validation.

| Quantity / 参数 | Published value / 公布值 |
|---|---|
| Active membrane area / 有效面积 | 37 m² |
| Feed NaCl / 进水 NaCl | 32,000 ppm |
| Pressure / 压力 | 55 bar (800 psi, rounded in source) |
| Temperature / 温度 | 25°C |
| Element recovery / 单元件回收率 | 8% |
| Permeate / 产水 | 28.4 m³/day |
| Stabilized salt rejection / 稳定脱盐率 | 99.8% |
| Minimum rejection / 最低脱盐率 | 99.65% |
| Boron / 硼 | 5 ppm feed, 92% rejection; excluded here |

数据表说明单支元件产水量可能变动，但不低于标称值的 85%。这不是对称置信区间。本模型按 32,000 ppm 约等于 32 kg/m³、恒密度 1000 kg/m³ 处理，保留 ppm 定义和真实盐水密度带来的换算误差。pH 8 与硼存在于原测试条件中，但不进入本二组分模型；不能据此判断硼去除或饮水安全。

## 2. 工况与初始参数 / Operating basis

模拟为稳态，无动态初始条件。入口边界为 32 g/L NaCl、25°C、14.79167 m³/h；进料流量由标称产水 / 8% 回收率推得。设计情景采用 6 支串联、总膜面积 222 m²、入口压力 60 bar、渗透侧表压 0 bar。55 和 60 bar 都作为跨膜压力的工程表压基准。

Steady axial model, with no time-domain initial conditions. Six serial elements, no interstage feed or recycle, and mixed collection of local permeate streams.

| Assumed parameter / 假设参数 | Value / 数值 |
|---|---|
| Liquid-film mass transfer k / 液膜传质 | 0.15 m/h |
| Osmotic coefficient phi / 渗透系数 | 0.93, constant |
| Pressure loss / 单支膜压降 | 0.15 bar |
| Pump efficiency / 高压泵效率 | 85% |
| Pressure exchanger efficiency / 压力交换效率 | 95% |
| Density / 密度 | 1000 kg/m³, constant |
| Pyomo mesh / 离散网格 | 30, 60, 120 cells |

以上传质、热力学近似与设备效率都是情景假设，未由数据表给出。标定 A = {A*1000:.5f} L m⁻² h⁻¹ bar⁻¹；B = {B*1000:.5f} L m⁻² h⁻¹。因为只有两个性能目标，固定 k、phi 和压降后拟合 A、B；不能同时辨识这些未知参数。

![Process flowsheet](figures/flowsheet.png)

## 3. 建模与计算原理 / Model equations

液态反渗透采用溶解扩散与膜表面浓差极化方程。与 WaterTAP 官方说明的 SD / film 方程形式一致。本实现是在 IDAES FlowsheetBlock 上编写自定义 Pyomo 方程，并用 IPOPT 求解；没有调用 WaterTAP 原生 RO 单元。SciPy DOP853 提供独立参考积分。

Engineering units: Q in m³/h, C in kg/m³, membrane coordinate a in m², J in m/h, pressure in bar. The reported water flux is the dilute-permeate volumetric-flux approximation.

$$J_v=A[(P_f-P_p)-(\pi_m-\pi_p)]$$

$$J_s=B(C_m-C_p),\qquad C_p=J_s/J_v$$

$$C_m=C_p+(C_b-C_p)\exp(J_v/k)$$

$$\pi(C)=2\phi RTC/M_{{NaCl}},\qquad M_{{NaCl}}=0.05844277\ \mathrm{{kg/mol}}$$

渗透压公式输出 Pa，模型中除以 100,000 转为 bar；NaCl 解离系数取 2，phi 为经验近似。膜表面盐度而非主体盐度进入渗透压差。

$$\frac{{dQ}}{{da}}=-J_v,\qquad \frac{{d(QC_b)}}{{da}}=-J_v C_p$$

$$P_f(a)=P_{{in}}-\Delta P_{{element}}\,a/A_{{element}}$$

水与盐组分均做守恒检查。Pyomo 使用隐式中点离散；初始化采用参考积分。模型自由度为 0，记录求解器终止状态和约束残差。

$$R=Q_p/Q_f,\qquad r_s=1-C_{{p,mixed}}/C_f$$

$$SEC_0=\frac{{P_f Q_f}}{{36\eta_p Q_p}}$$

$$SEC_{{PX}}=\frac{{P_f Q_f-\eta_{{PX}}P_bQ_b}}{{36\eta_p Q_p}}$$

SEC 单位为 kWh/m³。压力交换器情景以回收压力功抵扣高压泵液压负荷；不含详细旁路、混合损失、增压泵及效率曲线。不含取水、预处理、后处理和其他辅机用电。等温模型未求解热量衡算；这些数值是压力功估计。

## 4. 标定与预测 / Calibration and prediction

![Manufacturer calibration](figures/calibration.png)

图中虚线为厂商面积平均标称通量，实线为标定后局部通量预测；没有把局部预测当成实验测量。拟合目标为 log(预测产水/28.4) 与 log(预测产水盐度/64)，同等权重。

| Baseline prediction / 基准预测 | Value / 数值 |
|---|---|
| Product / 产水 | {s['permeate_m3_day']:.3f} m³/day |
| Recovery / 回收率 | {s['recovery']*100:.3f}% |
| Mixed product NaCl / 产水盐度 | {s['permeate_mg_L']:.3f} mg/L |
| Salt rejection / 脱盐率 | {s['rejection']*100:.4f}% |
| Brine NaCl / 浓水盐度 | {s['brine_g_L']:.3f} g/L |
| Feed osmotic pressure / 进水渗透压 | {s['feed_osmotic_bar']:.3f} bar |
| SEC without ERD / 无能量回收 | {s['sec_no_erd_kWh_m3']:.3f} kWh/m³ |
| SEC with assumed PX / 假设压力交换器 | {s['sec_pressure_exchanger_kWh_m3']:.3f} kWh/m³ |

厂商数据表没有六支串联膜的实测结果，因此不能把下面的串联系统结果称为实际验证。在同样的 55 bar 入口压力下，本模型预测六支串联产水 {standard_train['permeate_m3_day']:.3f} m³/day、回收率 {standard_train['recovery']*100:.2f}%、混合产水盐度 {standard_train['permeate_mg_L']:.2f} mg/L。简单将单元件标称产水量乘以 6 得到 170.4 m³/day，会高估串联结果约 {100*(1-standard_train['permeate_m3_day']/(6*28.4)):.1f}%；这是因为后段主体盐度、膜面浓差极化和渗透压逐步升高。60 bar 基准情景相对该线性估算低 {100*(1-s['permeate_m3_day']/(6*28.4)):.1f}%，但压力更高，不能与 55 bar 标称点直接作一一对应的误差判断。

The one-element calibration reproduces the manufacturer nominal flow and rejection by construction. It is a calibration check, not independent validation. The six-element train comparison is a model prediction because no matching train measurement was supplied.

![RO performance](figures/ro_performance.png)

沿程取走水使主体及膜表面盐度升高，因此渗透压升高、净驱动力下降、通量衰减。后段局部产水盐度比前段高。混合产水盐度按产水流量加权，不能简单平均局部浓度。提高入口压力通常提高本模型的回收率；能耗由泵、浓水流量和压力回收共同决定。

## 5. 合理性与数值检查 / Checks and limitations

盐衡算误差 {s['salt_balance_kg_h']:.3e} kg/h；水衡算误差 {s['water_balance_kg_h']:.3e} kg/h。参考积分加严容差的产水相对差 {checks['reference_refinement_relative']:.3e}。120 格 Pyomo 与参考积分的产水相对差 {checks['pyomo_relative_error']:.3e}。完整网格与残差见 convergence.json。

数值收敛检验证明同一方程组求解稳定，并不能证明模型能够准确预测真实海水装置。这里没有独立工况实验验证；缺少真实海水各离子、非理想活度、膜污染、压降关联式及膜寿命数据。

Sensitivity runs below hold fitted A and B fixed. These are assumption tests, not confidence intervals or additional measured data.

| Case / 情景 | Product m³/day | Recovery % | Product mg/L |
|---|---:|---:|---:|
{table}

![Assumption sensitivity](figures/sensitivity.png)

32 g/L NaCl 只代表海水级盐度的等效体系。模型不能预测 Na/Mg、Li/Mg 或硫酸根/氯离子的选择性。离子分离需要各离子组成、活度、膜电荷、分配与迁移参数，以及电中性约束；可进一步采用纳滤 DSPM-DE、电渗析 Nernst-Planck 或水相离子交换模型。真实海水还应考虑结垢及硼；本案例不作为饮水合格证明。

## 6. 复现与资料 / Reproduction and sources

Run from the repository root in the idaes-process environment:

```bash
python scripts/run_seawater_ro_demo.py
python scripts/render_reports.py --only seawater_ro_report
python -m pytest -q
```

输入、数据转录、标定、扫描、物料流与求解日志均保存在本结果目录。源 PDF 不作为自有许可文件重新分发；提供原始链接、版本、页码与 SHA-256，便于复查。

1. [DuPont original product data sheet](https://www.dupont.com/content/dam/dupont/amer/us/en/water-solutions/public/documents/en/RO-FilmTec-SW30HRLE-400-PDS-45-D00967-en.pdf), Rev. 8, January 2026, pp. 1-2.
2. [WaterTAP reverse osmosis equations](https://watertap.readthedocs.io/en/stable/technical_reference/unit_models/reverse_osmosis_0D.html), WaterTAP 1.7.0 documentation accessed 2026-09-13; used for equation form, not parameter values.
'''
    # Rebuild the equation block from character codes so Python string escaping cannot corrupt LaTeX commands.  # 用字符码重建公式，避免 Python 字符串转义破坏 LaTeX 命令
    bs = chr(92)  # 表示反斜杠，供 Markdown 数学公式使用
    formulas = "\n\n".join((  # 统一生成报告中的可渲染方程块
        "$$J_v=A[(P_f-P_p)-(" + bs + "pi_m-" + bs + "pi_p)]$$",
        "$$J_s=B(C_m-C_p)," + bs + "qquad C_p=J_s/J_v$$",
        "$$C_m=C_p+(C_b-C_p)" + bs + "exp(J_v/k)$$",
        "$$" + bs + "pi(C)=2" + bs + "phi RTC/M_{NaCl}," + bs + "qquad M_{NaCl}=0.05844277" + bs + " " + bs + "mathrm{kg/mol}$$",
        "$$" + bs + "frac{dQ}{da}=-J_v," + bs + "qquad " + bs + "frac{d(QC_b)}{da}=-J_v C_p$$",
        "$$P_f(a)=P_{in}-" + bs + "Delta P_{element}" + bs + ",a/A_{element}$$",
        "$$R=Q_p/Q_f," + bs + "qquad r_s=1-C_{p,mixed}/C_f$$",
        "$$SEC_0=" + bs + "frac{P_f Q_f}{36" + bs + "eta_p Q_p}$$",
        "$$SEC_{PX}=" + bs + "frac{P_f Q_f-" + bs + "eta_{PX}P_bQ_b}{36" + bs + "eta_p Q_p}$$",
    ))
    formula_start = text.index("Engineering units:")  # 定位英文单位说明及其后的公式区域
    formula_end = text.index("\n\nSEC ", formula_start)  # 定位公式后的能耗解释段落
    units_end = text.index("\n\n", formula_start)  # 保留英文单位说明本身
    text = text[:units_end] + "\n\n" + formulas + text[formula_end:]  # 替换损坏公式并保持报告段落顺序
    (out/'report.md').write_text(text,encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--spec',type=Path,default=ROOT/'assets/templates/seawater_ro.yaml')
    ap.add_argument('--output-dir',type=Path,default=ROOT/'demo_results/seawater_ro')
    args=ap.parse_args()
    out=args.output_dir
    (out/'figures').mkdir(parents=True,exist_ok=True)
    spec=load_spec(args.spec)
    p=parameters(spec)
    result=run_model(spec)
    write_result_bundle(result,spec,out)
    s,frame=result['summary'],result['profiles']
    A,B,cal,calframe=calibrate(spec)
    calframe.to_csv(out/'calibration_profiles.csv',index=False)
    save_json(out/'calibration.json',dict(A_m_h_bar=A,B_m_h=B,performance=cal,objective='equal-weight log relative flow and product concentration',evidence='two nominal targets; no independent validation'))
    d=spec.get('calibration')
    pd.DataFrame([dict(metric='permeate_m3_day',value=d['permeate_m3_day'],source_page=1),dict(metric='salt_rejection_fraction',value=d['rejection'],source_page=1),dict(metric='feed_NaCl_ppm',value=32000,source_page=1),dict(metric='area_m2',value=37,source_page=1),dict(metric='pressure_bar',value=55,source_page=1),dict(metric='temperature_C',value=25,source_page=1),dict(metric='recovery_fraction',value=.08,source_page=1)]).to_csv(out/'manufacturer_data.csv',index=False)
    save_json(out/'sources.json',dict(provenance=spec.get('provenance'),accessed='2026-09-13',source_sha256='a9cbf1641204b79629a27475d6046ab64f6f81bb58227623add05cc30f10ab9c',method_url='https://watertap.readthedocs.io/en/stable/technical_reference/unit_models/reverse_osmosis_0D.html'))
    sweep=pd.DataFrame([dict(pressure_bar=float(pr),**simulate(dict(p,pressure_bar=float(pr)),A,B)[0]) for pr in np.linspace(45,75,16)])
    sweep.to_csv(out/'pressure_sweep.csv',index=False)
    cases=[('baseline',{}),('low film transfer',{'mass_transfer_m_h':.10}),('high film transfer',{'mass_transfer_m_h':.20}),('ideal osmotic coefficient',{'osmotic_coefficient':1.0}),('higher pressure loss',{'pressure_drop_bar_per_element':.30})]
    sensitivity=pd.DataFrame([dict(case=name,**simulate(dict(p,**change),A,B)[0]) for name,change in cases])
    sensitivity.to_csv(out/'sensitivity.csv',index=False)
    standard_train,_=simulate(dict(p,pressure_bar=55.0),A,B)
    # Solver output stays in memory so result bundles remain portable across machines.  # 保持结果包可移植，不把本机求解器路径写入文件
    pyomo=[solve_pyomo(dict(p,cells=n),A,B) for n in (30,60,120)]  # 记录终止状态、自由度和方程残差即可复核离散化
    refined,_=simulate(p,A,B,rtol=1e-11)
    checks=dict(pyomo=pyomo,reference_refinement_relative=abs(refined['permeate_m3_day']/s['permeate_m3_day']-1),pyomo_relative_error=abs(pyomo[-1]['permeate_m3_day']/s['permeate_m3_day']-1),standard_train_55_bar=standard_train,linear_six_element_nominal_m3_day=6*28.4,versions={k:importlib.metadata.version(k) for k in ('idaes-pse','pyomo','scipy','numpy')})
    assert checks['pyomo_relative_error']<1e-4
    assert all(x['dof']==0 and x['max_equation_residual_engineering_units']<1e-7 for x in pyomo)
    assert abs(s['salt_balance_kg_h'])<1e-7 and abs(s['water_balance_kg_h'])<1e-6
    save_json(out/'convergence.json',checks)
    plot_results(out,frame,sweep,calframe,sensitivity)
    report(out,s,A,B,checks,sensitivity,standard_train)
    print(json.dumps(dict(summary=s,verification=checks),indent=2))


if __name__=='__main__':
    main()
