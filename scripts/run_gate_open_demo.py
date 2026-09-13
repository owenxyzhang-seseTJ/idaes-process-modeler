#!/usr/bin/env python3
"""Reproduce thermal flexible-MOF PSA, numerical checks and engineering report."""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 使用无界面后端运行批量图形
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from idaes_process_modeler.engine import run_model
from idaes_process_modeler.spec import load_spec
from idaes_process_modeler.reporting import write_result_bundle
from idaes_process_modeler.models.gate_open_psa import parameters, equilibrium, CM3_G_TO_MOL_KG


def main():
    out = ROOT/'demo_results/gate_open_thermal_psa'
    spec = load_spec(ROOT/'assets/templates/gate_open_psa.yaml')
    cases = {}
    for name in ['baseline', 'refined', 'long_contact', 'fixed_geometry', 'fixed_gate_temperature']:
        s = spec.copy()
        if name == 'refined':
            s.data['numerics'].update(rtol=1e-9, atol=1e-12, max_step='0.5 s')
        elif name == 'long_contact':
            for step in s.data['cycle']:
                step['duration'] = '1800 s'
        elif name == 'fixed_geometry':
            s.data['material']['expansion_fraction'] = 0
        elif name == 'fixed_gate_temperature':
            s.data['thermal']['gate_temperature_shift'] = False
        r = run_model(s)
        write_result_bundle(r, s, out/name)
        cases[name] = r
        print(name, json.dumps(r['summary']), flush=True)
    a = cases['baseline']['summary']
    f = cases['refined']['summary']
    b = cases['long_contact']['summary']
    rows = []
    for name, r in cases.items():
        d = r['profiles']
        d = d[d.cycle == d.cycle.max()]
        z = r['summary']
        rows.append(dict(case=name, css=z['css_converged'], cycles=z['cycles_run'],
            working_capacity=z['working_capacity_cm3_stp_g'], product_mol=z['co2_product_mol'],
            purity=z['purity'], recovery=z['recovery'], temperature_min_k=d.temperature_k.min(),
            temperature_max_k=d.temperature_k.max(), max_volume_l=d.solid_volume_l.max(),
            max_length_um=d.crystal_length_um.max(), k_min_s=d.co2_k_eff_s.min(), k_max_s=d.co2_k_eff_s.max(),
            total_pressure_min_kpa=d.pressure_kpa.min(), total_pressure_max_kpa=d.pressure_kpa.max(),
            mass_error_mol=z['mass_balance_error'],
            energy_error_j=float(r['metrics'].energy_balance_error_j.abs().max())))
    table = pd.DataFrame(rows)
    table.to_csv(out/'comparison.csv', index=False)
    check = dict(product_relative_change=abs(f['co2_product_mol']/a['co2_product_mol']-1),
                 capacity_relative_change=abs(f['working_capacity_cm3_stp_g']/a['working_capacity_cm3_stp_g']-1))
    (out/'verification.json').write_text(json.dumps(check, indent=2)+'\n')
    _, p = parameters(spec)
    pressure = np.linspace(0, 20, 801)
    eq = np.array([equilibrium(np.array([v*1000, v*1000]), np.clip((v*1000-p['gate'])/p['width'], 0, 1), p) for v in pressure])/CM3_G_TO_MOL_KG  # 从本构生成参考曲线并转换为体积吸附单位
    pd.DataFrame({'partial_pressure_kpa': pressure, 'co2_cm3_stp_g': eq[:, 0], 'n2_cm3_stp_g': eq[:, 1]}).to_csv(out/'equilibrium_298K.csv', index=False)
    # Plots read the saved solver samples, without smoothing or fitted data.
    d = pd.read_csv(out/'baseline/profiles.csv')
    d = d[d.cycle == d.cycle.max()]
    t = (d.time_s-d.time_s.min())/60
    plt.rcParams.update({'font.size': 10, 'svg.fonttype': 'none', 'pdf.fonttype': 42})  # 统一字号并保持矢量文字可编辑
    fig, axes = plt.subplots(3, 2, figsize=(12, 11), constrained_layout=True)  # 创建六面板耦合过程图
    axes = axes.ravel()
    axes[0].plot(pressure, eq[:, 0], label=r'CO$_2$', color='#287D8E')  # 用青色表示参考温度下开门曲线
    axes[0].plot(pressure, eq[:, 1], label=r'N$_2$', color='#C47950')  # 用橙色表示低容量氮气曲线
    axes[0].set(xlabel='Component partial pressure (kPa)', ylabel=r'q (cm$^3$(STP) g$^{-1}$)', title='a  Equilibrium input at 298 K')  # 明确分压与参考温度
    axes[0].legend(frameon=False)  # 显示组分图例
    axes[1].plot(t, d.pressure_kpa, label='Total', color='#777777')  # 展示总压变化
    axes[1].plot(t, d.co2_partial_kpa, label=r'CO$_2$ partial', color='#287D8E')  # 展示动态组分分压
    axes[1].set(xlabel='Time in last cycle (min)', ylabel='Pressure (kPa)', title='b  1 bar adsorption / 5 kPa evacuation')  # 标明最终压力循环
    axes[1].legend(frameon=False)  # 区分总压与分压
    axes[2].plot(t, d.co2_loading_cm3_stp_g, label=r'CO$_2$', color='#287D8E')  # 展示动态二氧化碳负载
    axes[2].plot(t, d.n2_loading_cm3_stp_g, label=r'N$_2$', color='#C47950')  # 展示低压氮气释放
    axes[2].set(xlabel='Time in last cycle (min)', ylabel=r'q (cm$^3$(STP) g$^{-1}$)', title='c  Dynamic loading')  # 明确吸附量单位
    axes[2].legend(frameon=False)  # 标记两种气体
    axes[3].plot(t, d.temperature_k, color='#C47950')  # 展示吸附放热和解吸降温
    axes[3].set(xlabel='Time in last cycle (min)', ylabel='Bed temperature (K)', title='d  Effective heat: 40 kJ/mol CO2')  # 明确热量基准
    axes[4].plot(t, d.solid_volume_l, color='#6C67A5')  # 展示晶体膨胀带来的体积变化
    axes[4].set(xlabel='Time in last cycle (min)', ylabel='MOF envelope volume (L)', title='e  Flexible volume; constant 1.5 kg', ylim=(.995, 1.055))  # 采用完整体积范围避免夸大变化
    axes[5].plot(t, d.co2_k_eff_s, color='#287D8E')  # 展示长度与温度共同修正的传质系数
    axes[5].set(xlabel='Time in last cycle (min)', ylabel=r'Effective LDF k (s$^{-1}$)', title='f  Temperature + diffusion-length coupling')  # 标注耦合的动力学系数
    for ax in axes:
        ax.spines[['top', 'right']].set_visible(False)  # 简化图面边框
    fig.suptitle('Flexible MOF PSA | nonisothermal reduced-order scenario', fontsize=15)  # 明示非等温简化模型属性
    save(fig, out/'thermal_psa')
    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)  # 单独保存吸附解吸速率曲线
    ax.plot(t, d.co2_rate_cm3_stp_g_s, color='#287D8E')  # 正值为吸附负值为解吸
    ax.set(xlabel='Time in last cycle (min)', ylabel=r'dq/dt (cm$^3$(STP) g$^{-1}$ s$^{-1}$)', title='CO2 uptake / release rate')  # 说明速率单位
    save(fig, out/'uptake_rate')
    fig, ax = plt.subplots(figsize=(12, 3.5), constrained_layout=True)  # 创建设备与物流流程图
    ax.set(xlim=(0, 12), ylim=(0, 3))  # 固定示意图坐标
    ax.axis('off')  # 隐藏无物理意义的坐标轴
    for x, label in [(1.5, 'FEED\n15% CO2 / 85% N2\n1 bar, 298 K'), (6, 'V-101 flexible MOF\n1.5 kg; 1.00–1.05 L\nHeat exchange UA = 10 W/K'), (10.5, 'ADS: raffinate\nDES: vacuum outlet\n5 kPa target')]:
        ax.text(x, 1.5, label, ha='center', va='center', bbox=dict(boxstyle='round,pad=0.6', facecolor='#E4F0F1', edgecolor='#287D8E'))  # 绘制流程节点与设备参数
    for start, end in [((3, 1.5), (4.2, 1.5)), ((7.8, 1.5), (9, 1.5))]:
        ax.annotate('', xy=end, xytext=start, arrowprops=dict(arrowstyle='->', color='#287D8E', lw=2))  # 标示进料和产品流向
    ax.set_title('Conceptual flowsheet | feed valve closes during evacuation')  # 说明抽气时关闭进料
    save(fig, out/'flowsheet')
    r0 = rows[0]
    md = '# 柔性 MOF 非等温 PSA 报告\n\n'
    md += '最终工况：15% CO₂＋85% N₂ 在总压 1 bar 下吸附，关闭进料，直接抽气至总压 5 kPa。无混合气吹扫。\n\n'
    md += '模型已接入插件 run_model；使用 SciPy BDF，IDAES/Pyomo 环境已检查可用，但柔性单元尚非 IDAES 原生单元。所有结果为假设参数下的模拟。\n\n'
    md += '## 计算结果\n\n|工况|工作容量 cm³(STP)/g|CO₂ mol/周期|抽气产品 CO₂ %|回收率 %|温度 K|CSS 周期|\n|---|---:|---:|---:|---:|---|---:|\n'
    for row in rows:
        md += f"|{row['case']}|{row['working_capacity']:.4f}|{row['product_mol']:.5f}|{row['purity']*100:.2f}|{row['recovery']*100:.2f}|{row['temperature_min_k']:.2f}–{row['temperature_max_k']:.2f}|{row['cycles']}|\n"
    md += '\nbaseline：600 s 吸附＋600 s 抽气；refined：同工况更严求解；long_contact：各1800 s；fixed_geometry：取消5%膨胀，保留门控与热模型；fixed_gate_temperature：保留能量方程，但关闭门控阈值温度外推。后两项仅用于识别模型假设影响。\n\n'
    md += '![耦合结果](thermal_psa.png)\n\n![速率](uptake_rate.png)\n\n## 初始参数与来源\n\n'
    md += '用户给定：实体体积1 L、密度1.5 g/cm³、开门膨胀5%；CO₂在5 kPa为1、15 kPa为40 cm³(STP)/g，10–11 kPa陡升；N₂约1 cm³(STP)/g；吸附总压1 bar、解吸总压5 kPa；有效热约40 kJ/mol。\n\n'
    md += '假设：1 L指晶体实体包络体积，因此质量1.5 kg；初始床空隙率0.4，刚性容器1.667 L；298 K进气／环境；CO₂/N₂参考LDF系数0.02/0.05 s⁻¹；结构响应0.1 s⁻¹；晶体特征长度10 μm；扩散活化能15 kJ/mol；固体热容1000 J/(kg·K)、容器热容500 J/K、气体Cv=25 J/(mol·K)、UA=10 W/K。吸附基准流量0.05 mol/s，入口控制器可补气维持压力；阀导纳0.001 mol/(s·Pa)，尚未匹配实际真空泵能力。\n\n'
    md += 'STP=273.15 K、1 atm。39 cm³(STP)/g对应58.5 L(STP)，约2.610 mol；这是298 K平衡工作容量，不是任何有限周期的保证值。低于5 kPa分压的CO₂/N₂容量线性延拓至零，不把N₂低容量平台延伸到真空零压。实际抽气末CO₂分压小于等于总压5 kPa，故末负载可略小于1。\n\n'
    md += r'''## 晶体体积与传质

膨胀时质量保持不变，实体体积增加。在各向同性膨胀假设下：

\[
V_s=V_{s,0}(1+0.05f),\qquad
L=L_0(1+0.05f)^{1/3},\qquad
V_g=V_{vessel}-V_s.
\]

完全开门时 10 um -> 10.164 um；若扩散系数 D 不变，仅扩散长度效应为：

\[
\frac{k_{geom}}{k_{geom,0}}=(1.05)^{-2/3}=0.9680.
\]

因此几何长度单独使 k 降低约 3.2%；密度降至 1.4286 g cm$^{-3}$，床层空隙率从 0.40 变为约 0.37。晶体尺寸使用一致的特征长度定义；孔口开度对 D、缺陷、裂纹和粒间阻力的额外影响需要数据。

温度和几何长度共同修正 LDF 系数：

\[
k_i(T,f)=k_{i,0}\exp\left[-\frac{E_{a,i}}{R}\left(\frac{1}{T}-\frac{1}{T_0}\right)\right](1+0.05f)^{-2/3},
\qquad
\frac{dq_i}{dt}=k_i(T,f)(q_i^*-q_i).
\]

'''
    md += r'''## 热与结构模型

40 kJ mol$^{-1}$ 暂按每摩尔 CO2 的有效吸附/结构热量幅值处理，包含结构变化相关热，不再额外加入一份相变热。未按每摩尔框架化学式计算；若该数值实际以框架摩尔为基准，需要补充化学式和摩尔质量。

控制体能量采用：

\[
U=(mC_s+C_{wall}+n_gC_v)T-mE_{bind}q_{CO_2},
\qquad E_{bind}=40000-R T_0.
\]

\[
\frac{dU}{dt}=F_{in}C_pT_{in}-F_{out}C_pT-UA(T-T_{amb}),
\qquad C_p=C_v+R.
\]

吸附放热、解吸吸热、抽气显热和床壁换热均进入；晶体/气相间的膨胀功作为控制体内部能量耦合，不再当成外部功重复加入。当前没有计算真空泵功。

门控在参考温度 T$_0$=298 K 时为：

\[
f^*=\operatorname{clip}\left(\frac{p_{CO_2}-10\,\mathrm{kPa}}{1\,\mathrm{kPa}},0,1\right),
\qquad
\frac{df}{dt}=k_f(f^*-f).
\]

非等温时使用工程化的温度平移：

\[
p_{gate}(T)=p_{gate}(T_0)\exp\left[\frac{H_{eff}}{R}\left(\frac{1}{T_0}-\frac{1}{T}\right)\right].
\]

升温提高开门压力、降温降低开门压力。这不是由柔性框架自由能推导出的相边界；`fixed_gate_temperature` 对照用于显示这一假设的影响。没有关门滞后数据，因此没有加入固有滞后环，但有限速率仍会产生动态滞后。

'''
    md += r'''## 建模、衡算与流程

![流程图](flowsheet.png)

气相 n$_i$、固相 q$_i$、结构 f 和温度 T 共同积分：

\[
p_i=\frac{n_iRT}{V_g},\qquad y_i=\frac{n_i}{\sum_j n_j},
\qquad
\frac{dn_i}{dt}=F_{in}y_{i,in}-F_{out}y_i-m\frac{dq_i}{dt}.
\]

抽气时 F$_{in}$=0；出口按目标压力的有限导纳移除实时组成的气体，不把解吸气相固定为 15% CO2。

回收率和产品纯度分别定义为：

\[
\eta_{CO_2}=\frac{N_{CO_2,out}^{des}}{N_{CO_2,in}^{ads}},
\qquad
x_{CO_2,des}=\frac{N_{CO_2,out}^{des}}{\sum_iN_{i,out}^{des}}.
\]

固相工作容量单独使用周期内 q$_{max}$-q$_{min}$ 计算，不把容器初始气相库存当成固相捕集量。

'''
    md += f"## 数值检查与边界\n\n末周期CSS差={a['css_state_delta']:.3e}，基准最大组分衡算差={r0['mass_error_mol']:.3e} mol；最大能量积分差={r0['energy_error_j']:.3e} J。求解器BDF，rtol=1e−7、atol=1e−10、最大步长2 s；refined改为1e−9、1e−12、0.5 s，产品量相对变化={check['product_relative_change']:.3e}，工作容量相对变化={check['capacity_relative_change']:.3e}。\n\n"
    md += f"基准最后周期总压范围{r0['total_pressure_min_kpa']:.4f}–{r0['total_pressure_max_kpa']:.4f} kPa；温度{r0['temperature_min_k']:.2f}–{r0['temperature_max_k']:.2f} K；MOF最大体积{r0['max_volume_l']:.6f} L。记录实际压力，阀模型并非严格代数恒压。\n\n"
    md += '这些检查证明数值方程闭合，不能验证热容、门控温度关系、扩散参数或工业性能。没有实验混合气等温线、孔内竞争模型、分布式温度／浓度梯度、吸附热分离测量及疲劳数据；应优先用DSC/吸附量热、原位变温结构及动力学数据替换假设。\n\n'
    md += '## 文件与复现\n\n模板 assets/templates/gate_open_psa.yaml；运行 `conda run -n idaes-process python scripts/run_gate_open_demo.py`。baseline/refined/long_contact及两个敏感性目录保存每个工况YAML、profiles.csv、streams.csv、metrics.csv与summary.json；comparison.csv和verification.json为可追溯比较。旧gate_open_psa目录保留之前吹扫试算，已被本最终工况取代。\n'
    (out/'report.md').write_text(md, encoding='utf-8')
    if not table.css.all() or max(check.values()) > .001 or table.mass_error_mol.max() > 1e-7 or table.energy_error_j.max() > 1:
        raise RuntimeError('Numerical verification failed; inspect saved files')


def save(fig, stem):
    for ext in ['png', 'svg', 'pdf']:
        fig.savefig(stem.with_suffix('.'+ext), dpi=180, bbox_inches='tight')  # 输出高清预览和矢量图
    plt.close(fig)  # 释放图形资源


if __name__ == '__main__':
    main()
