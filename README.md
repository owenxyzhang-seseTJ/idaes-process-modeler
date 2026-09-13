# IDAES Process Modeler

IDAES Process Modeler is a Codex plugin and Python package for auditable
chemical-process modeling with IDAES, Pyomo/Pyomo.DAE, and explicit
reduced-order models. It supports fixed-bed adsorption, PSA/VSA/TSA cycle
maps, membrane separation, membrane reactors, parameter estimation, sweeps,
validation reports, and guarded IDAES reference cases.

IDAES Process Modeler 是一个面向 Codex 的插件和 Python 工具包，用于建立可审计的
化工过程模型。它同时提供 IDAES、Pyomo/Pyomo.DAE 接口和明确标注的 reduced-order
模型，覆盖固定床吸附、PSA/VSA/TSA 循环、膜分离、膜反应器、参数估计、参数扫描和
数值验证报告。

The package keeps a strict evidence boundary. A successful numerical solve is a
solver result; CSS convergence is a numerical criterion; a reduced-order case
is a scenario study. None of these is experimental or industrial validation
without matching measurements or a benchmark.

本项目严格区分证据等级。求解器成功只说明数值问题完成；CSS 收敛只说明循环状态满足
数值判据；reduced-order 结果只是情景模拟。没有匹配实验或基准时，不把这些结果称为
实验验证或工业验证。

## Installation and first check / 安装与首次检查

Create the recommended Conda environment and install IDAES extensions before
constructing a process model:

先建立推荐的 Conda 环境，并在建模前安装 IDAES 扩展：

```bash
conda env create -f environment.yml
conda activate idaes-process
idaes get-extensions
python scripts/check_environment.py --strict
python -m pip install -e '.[test]'
```

The strict check must find IDAES, Pyomo, Pyomo.DAE, and a usable solver. On
Apple Silicon, the IDAES-managed IPOPT executable is preferred when the Conda
solver has compatibility problems. The extension path is discovered at runtime;
no local machine path is stored in result manifests.

严格检查必须找到 IDAES、Pyomo、Pyomo.DAE 和可用求解器。在 Apple Silicon 上，如果
Conda 中的 IPOPT 存在兼容性问题，优先使用 IDAES 管理的求解器。运行时动态查找扩展
路径，结果 manifest 不保存本机绝对路径。

## Quick start / 快速开始

Run the original deterministic demonstrations:

运行原有的确定性 demo：

```bash
python demos/demo_fixed_bed.py --output-dir demo_results/fixed_bed
python demos/demo_psa.py --output-dir demo_results/psa
python demos/demo_membrane.py --output-dir demo_results/membrane
python demos/demo_membrane_reactor.py --output-dir demo_results/membrane_reactor
python scripts/plot_demo_results.py
python -m pytest -q
```

Run the flexible gate-open MOF PSA demonstration:

运行柔性 gate-open MOF PSA demo：

```bash
python scripts/run_gate_open_demo.py
```

The command creates baseline, solver-refined, long-contact, fixed-geometry,
and fixed-gate-temperature cases under
`demo_results/gate_open_thermal_psa/`. It writes YAML inputs, machine-readable
CSV/JSON result bundles, PNG/SVG/PDF figures, and a bilingual technical report.

该命令在 `demo_results/gate_open_thermal_psa/` 下生成 baseline、求解器加密、长接触时间、
固定几何和固定门控温度五个工况，并保存 YAML 输入、CSV/JSON 结果、PNG/SVG/PDF 图和
中英文技术报告。

## Repository map / 目录结构

| Path | English | 中文 |
|---|---|---|
| `.codex-plugin/` | Codex plugin metadata | Codex 插件元数据 |
| `skills/idaes-process-modeler/` | Skill instructions and references | Skill 说明与建模参考 |
| `src/idaes_process_modeler/` | Reusable Python package | 可复用 Python 包 |
| `assets/templates/` | YAML/JSON model specifications | YAML/JSON 模型输入模板 |
| `demos/` | Small runnable demo entry points | 可直接运行的 demo 入口 |
| `scripts/` | Validation, plotting, report and sweep tools | 校验、绘图、报告和扫描脚本 |
| `tests/` | Regression and physics-contract tests | 回归测试和物理契约测试 |
| `demo_results/` | Reproducible result snapshots and rendered reports | 可追溯结果快照与渲染报告 |
| `runs/` | Local runtime output and sweeps | 本地运行输出和参数扫描目录 |

Each standard result bundle contains `summary.json`, `streams.csv`,
`profiles.csv`, `metrics.csv`, `convergence.json`, `model_spec.yaml`, and a
`figures/` directory. Paths in reports are relative so a checkout can be moved
to another machine.

标准结果包包含 `summary.json`、`streams.csv`、`profiles.csv`、`metrics.csv`、
`convergence.json`、`model_spec.yaml` 和 `figures/`。报告使用相对路径，因此整个仓库
移动到另一台机器后仍可读取。

## Model routing / 模型路由

Use `$idaes-process-modeler` when a request involves IDAES/Pyomo process
models, dynamic simulation, adsorption cycles, membranes, reactors, fitting,
optimization, or process validation. The Skill requires a structured
specification before model construction and labels parameters by provenance:
user input, experiment, literature, fit, or assumption.

当任务涉及 IDAES/Pyomo 过程模型、动态模拟、吸附循环、膜、反应器、拟合、优化或
过程验证时，使用 `$idaes-process-modeler`。Skill 要求先形成结构化输入，并明确每个
参数来自用户、实验、文献、拟合还是假设。

The standard routes are:

标准模型路线如下：

- `fixed_bed_adsorption`: 1-D convection/dispersion with adsorption storage,
  LDF kinetics, selectable isotherms, and Ergun diagnostic pressure drop.
- `psa`, `vsa`, `tsa`: data-driven single-bed cycle maps with CSS diagnostics.
- `membrane_separation`: ideal-gas co-current membrane material balance.
- `membrane_reactor`: reduced-order reaction plus selective H2 removal.
- `gate_open_psa`: binary, nonisothermal flexible-solid tank PSA described below.
- `bubbling_fluidized_bed`: guarded extension point; local bubble dynamics are
  outside this reduced-order package.

- `fixed_bed_adsorption`：一维对流/弥散、吸附储存、LDF 动力学、可选等温线和 Ergun 压降诊断。
- `psa`、`vsa`、`tsa`：数据驱动的单床循环 map 与 CSS 诊断。
- `membrane_separation`：理想气体并流膜分离物料衡算。
- `membrane_reactor`：反应与选择性移除 H₂ 的 reduced-order 模型。
- `gate_open_psa`：下文介绍的二元、非等温柔性固体罐式 PSA。
- `bubbling_fluidized_bed`：受保护的扩展点；局部气泡动力学不在当前 reduced-order 包范围内。

## Flexible gate-open MOF PSA / 柔性 gate-open MOF PSA

### User-defined basis / 用户给定基础

`assets/templates/gate_open_psa.yaml` is the canonical input template. It uses
the following interpretation of the request:

`assets/templates/gate_open_psa.yaml` 是正式输入模板，当前采用以下参数解释：

| Quantity | Value | 说明 |
|---|---:|---|
| Solid volume / MOF 实体体积 | 1.0 L | Initial crystal/solid envelope volume |
| MOF density / MOF 密度 | 1.5 g cm⁻³ | Solid mass = 1.5 kg |
| Feed / 吸附进料 | 15% CO₂ + 85% N₂ | Total pressure = 1 bar |
| Gate onset / 开门起点 | CO₂ partial pressure 10 kPa | Gate is expressed in CO₂ partial pressure |
| Gate width / 陡升区间 | 1 kPa | 10 to 11 kPa partial pressure |
| High-pressure uptake / 高压吸附量 | 40 cm³(STP) g⁻¹ CO₂ | At 15 kPa CO₂ partial pressure |
| Low-pressure uptake / 低压吸附量 | 1 cm³(STP) g⁻¹ CO₂ | At 5 kPa CO₂ partial pressure |
| N₂ uptake / N₂ 吸附量 | 1 cm³(STP) g⁻¹ | Low-capacity assumption |
| Expansion / 开门膨胀 | 5% volume | Solid volume reaches 1.05 L |
| Adsorption / 吸附压力 | 1 bar total | CO₂ feed partial pressure = 15 kPa |
| Evacuation / 抽气解吸 | 5 kPa total target | Feed is closed during evacuation |

The cycle is therefore **1 bar adsorption -> closed-feed evacuation to 5 kPa ->
1 bar adsorption**. The 5 kPa value is the total evacuation target. The model
does not force the gas composition to remain 15% CO₂ during evacuation; it
integrates component inventories and calculates the evolving partial pressures.

因此循环是 **1 bar 吸附 -> 关闭进料并抽气至 5 kPa -> 重新吸附**。5 kPa 是抽气总压
目标。模型不会在抽气阶段强行保持 15% CO₂，而是积分各组分气相库存并计算动态分压。

### Equations / 计算方程

The demo is a SciPy BDF reduced-order model with gas inventories, adsorbed
loadings, a structural state `f`, and temperature `T`:

该 demo 使用 SciPy BDF，对气相库存、吸附量、结构状态 `f` 和温度 `T` 进行积分：

$$
f^* = \operatorname{clip}\left(\frac{p_{CO_2}-10\,\mathrm{kPa}}{1\,\mathrm{kPa}},0,1\right),\qquad
\frac{df}{dt}=k_f(f^*-f).
$$

$$
V_s=V_{s,0}(1+0.05f),\qquad
L=L_0(1+0.05f)^{1/3},\qquad
V_g=V_{vessel}-V_s.
$$

$$
\frac{dq_i}{dt}=k_i(T,f)(q_i^*-q_i),\qquad
k_i(T,f)=k_{i,0}\exp\left[-\frac{E_{a,i}}{R}\left(\frac{1}{T}-\frac{1}{T_0}\right)\right](1+0.05f)^{-2/3}.
$$

$$
p_i=\frac{n_iRT}{V_g},\qquad
\frac{dn_i}{dt}=F_{in}y_{i,in}-F_{out}y_i-m\frac{dq_i}{dt}.
$$

The 40 kJ mol⁻¹ value is treated as an effective CO₂ adsorption/structural
heat magnitude. It is not added twice as both adsorption heat and a separate
phase-transition heat. The energy closure uses solid heat capacity, wall heat
capacity, gas heat capacity, inlet/outlet sensible heat, and `UA` heat exchange.

40 kJ mol⁻¹ 暂按 CO₂ 吸附与结构变化合并后的有效热量幅值处理，不再把它重复加成
吸附热和独立相变热。能量方程包含固体热容、器壁热容、气体热容、进出口显热和 `UA`
换热项。

### Crystal-volume and mass-transfer coupling / 晶体体积与传质耦合

Expansion changes the solid volume at constant mass. Under an isotropic
expansion assumption, the characteristic crystal length changes with the cube
root of volume, and the diffusion-length contribution to the LDF coefficient
scales as `L⁻²`. The current 5% expansion therefore changes the characteristic
length by 1.64% and reduces this geometric contribution to `k` by about 3.2%
when diffusivity is held constant.

膨胀时质量保持不变，实体体积增加。在各向同性膨胀假设下，晶体特征长度按体积立方
根变化，LDF 传质系数中的扩散长度项按 `L⁻²` 变化。因此 5% 膨胀使特征长度增加
1.64%；若扩散系数不变，仅几何长度效应使 `k` 降低约 3.2%。

The model also includes an assumed temperature correction to the gate pressure.
Because gate hysteresis and a measured temperature-dependent phase boundary
were not supplied, the report includes a `fixed_gate_temperature` sensitivity
case. That comparison is an assumption sensitivity, not a material-property
measurement.

模型还加入了门控压力随温度变化的假设修正。由于没有提供门控滞后和实测温度依赖相边界，
报告同时给出 `fixed_gate_temperature` 敏感性工况。这个对照用于识别假设影响，不是材料
性质测量。

The older `demo_results/gate_open_psa/` directory is retained as a clearly
labelled historical purge-only trial for auditability. The final user-approved
configuration is `demo_results/gate_open_thermal_psa/`: closed-feed
evacuation to 5 kPa with nonisothermal crystal-volume and mass-transfer
coupling.

旧的 `demo_results/gate_open_psa/` 目录仅作为带混合气吹扫的历史试算快照保留，便于审计；
最终采用的用户确认工况是 `demo_results/gate_open_thermal_psa/`：关闭进料、抽气至 5 kPa，
并耦合非等温晶体体积变化与传质影响。

## Reports and rendered artifacts / 报告与渲染文件

### Seawater reverse osmosis / 海水反渗透脱盐

The aqueous `seawater_ro` demo uses **actual manufacturer nominal test data**
from the [DuPont SW30HRLE-400 January 2026 data sheet](https://www.dupont.com/content/dam/dupont/amer/us/en/water-solutions/public/documents/en/RO-FilmTec-SW30HRLE-400-PDS-45-D00967-en.pdf):
37 m², 32,000 ppm NaCl, 55 bar, 25°C, 8% recovery, 28.4 m³/day permeate,
and 99.8% stabilized salt rejection. The source is a product specification,
not a raw experimental dataset. Its URL, revision, page, transcription and
SHA-256 are recorded with the demo.

水相 `seawater_ro` demo 采用杜邦官方标称测试数据，先标定水与盐的透过系数，再预测
六支膜串联的性能。包含溶解扩散、渗透压、浓差极化、轴向浓缩和指定压降。SciPy
参考积分与 IDAES FlowsheetBlock 上的自定义 Pyomo/IPOPT 方程求解相互对照。
它不调用 WaterTAP 原生单元；拟合标称点也不等于独立实验验证。

```bash
conda run -n idaes-process python scripts/run_seawater_ro_demo.py
python scripts/render_reports.py --only seawater_ro_report
# General CLI: reference integration / 通用命令行参考积分
idaes-model run assets/templates/seawater_ro.yaml --output-dir runs/seawater_ro
```

Baseline scenario: 6 × 37 m², 60 bar, 32 g/L NaCl, 25°C, and 14.7917 m³/h
feed. Predicted product is approximately **146.6 m³/day**, recovery **41.3%**,
and mixed product NaCl **92.2 mg/L**. RO pressure-work electricity is about
**4.75 kWh/m³** without energy recovery or **2.14 kWh/m³** with an assumed
95%-efficient pressure exchanger and 85%-efficient pump. These estimates
exclude intake, pretreatment, post-treatment and auxiliary power.

基准预测：产水约 **146.6 m³/天**，回收率 **41.3%**，产水 NaCl 约 **92.2 mg/L**。
高压泵能耗估算为无回收 **4.75 kWh/m³**，假设配置压力交换器时 **2.14 kWh/m³**。
报告给出压力扫描、传质/渗透压/压降假设敏感性、水盐衡算及 30/60/120 格收敛。
浓度按恒密度将 ppm 近似换算为 kg/m³，传质和渗透系数为明确的情景假设。

This is NaCl-equivalent seawater, not a multi-ion seawater chemistry model.
It cannot predict Li/Mg or Na/Mg selectivity, boron removal, scaling, fouling,
or drinking-water compliance. Those extensions need ion-resolved data and
thermodynamic/transport models.

本例为等效 NaCl 脱盐，不代表真实海水的全部离子化学；不能据此判断 Li/Mg 选择性、
硼去除、结垢、污染或饮水合格。水相离子选择性分离需另建对应传输与热力学模型。

- [Input template / 输入模板](assets/templates/seawater_ro.yaml)
- [Source transcription / 厂商数据转录](demo_results/seawater_ro/manufacturer_data.csv)
- [Bilingual report / 中英文报告](demo_results/seawater_ro/report.md)
- [Rendered PDF / 公式排版 PDF](output/pdf/reports/seawater_ro_report.pdf)
- [Results figure / 结果图](demo_results/seawater_ro/figures/ro_performance.png)
- [Convergence / 数值验证](demo_results/seawater_ro/convergence.json)

### Report index / 报告索引

The main reports are available in both Markdown and rendered PDF form:

主要报告同时提供 Markdown 和渲染后的 PDF：

- [Original demos: Markdown](demo_results/technical_report/demo_technical_report.md)
- [Original demos: rendered PDF](output/pdf/reports/demo_technical_report.pdf)
- [Flexible MOF PSA: Markdown](demo_results/gate_open_thermal_psa/report.md)
- [Flexible MOF PSA: rendered PDF](output/pdf/reports/gate_open_thermal_psa_report.pdf)
- [Flexible MOF PSA: rendered page previews](output/preview/reports/)
- [Figure and result contact sheet](output/preview/report_contact_sheet.png)
- [Render manifest (repository-relative paths)](output/preview/report_render_manifest.json)

原有 demo 报告和柔性 MOF PSA 报告均已渲染为 PDF；公式、表格和报告内图像会在 PDF 中
按页面排版，不依赖 GitHub 对 Markdown 数学语法的支持。运行
`python scripts/render_reports.py` 可重新生成 PDF 与 PNG 页面预览。

The same render directory also contains the companion PDFs for the English figure plans,
method-search packets, and QA reports. The current render manifest covers eight Markdown
sources and 18 PDF pages in total. The temporary XeLaTeX build directory is deleted after
each run, and the manifest records only checkout-relative paths.

同一渲染目录还包含 English figure plan、method-search packet 和 QA report 的配套 PDF。
当前 manifest 覆盖 8 个 Markdown 源文件、共 18 页 PDF。每次运行结束后会删除 XeLaTeX
临时构建目录，manifest 只记录相对于仓库的路径，不写入本机绝对路径。

The gate-open figure exports are:

柔性 MOF PSA 图文件包括：

- `thermal_psa.{png,svg,pdf}`: equilibrium input, pressure, loading,
  temperature, volume, and effective LDF coefficient;
- `uptake_rate.{png,svg,pdf}`: CO₂ uptake/release rate;
- `flowsheet.{png,svg,pdf}`: Aspen-like conceptual process diagram.

## Validation and limitations / 验证与限制

The package performs preflight validation, state-bound checks, component
material-balance checks, energy-closure checks for the thermal demo, CSS checks,
and solver refinement checks. The current flexible-MOF run reached CSS in all
stored cases. The baseline/refined product and working-capacity changes were
about `4.5e-9` under the tighter BDF settings.

项目执行输入预检查、状态边界检查、组分物料衡算、热量闭合、CSS 和求解器加密检查。
当前柔性 MOF 各工况均达到 CSS；baseline 与 refined 在更严格 BDF 设置下的产品量和工作
容量相对变化约为 `4.5e-9`。

The current route is intentionally a reduced-order mixed-tank scenario. It
does not yet resolve axial concentration/temperature fronts, a competitive
mixture isotherm, a measured gate hysteresis loop, vacuum-pump power, particle
size distributions, crystal cracking, or an IDAES flexible-unit model. Replace
the assumed thermal and kinetic parameters with DSC/calorimetry, variable-
temperature adsorption, in-situ structural, and mass-transfer data before
using the model for design decisions.

当前路线是明确标注的 reduced-order 全混罐情景模型。它还没有解析轴向浓度/温度前沿、
竞争吸附等温线、实测门控滞后、真空泵功耗、粒径分布、晶体开裂或 IDAES 柔性单元。
用于工艺设计前，应以 DSC/吸附量热、变温吸附、原位结构和传质实验数据替换假设参数。

## Development and contribution / 开发与贡献

Run the full regression suite in the IDAES environment:

在 IDAES 环境中运行完整回归测试：

```bash
conda run -n idaes-process python -m pytest -q
python scripts/render_reports.py
```

When the optional `scientific-figure-team` skill is installed, run its Chinese
visual-comment validator on `scripts/run_gate_open_demo.py` before changing the
figure code.

Keep user data, fitted parameters, scenario assumptions, numerical evidence,
and physical validation in separate sections. New figures should preserve raw
machine-readable data, an English figure plan, a method-search packet, editable
SVG/PDF text, and a visual QA record.

新增模型或图时，请把用户数据、拟合参数、情景假设、数值证据和物理验证分开记录。新增
图应保留机器可读原始数据、英文 figure plan、method-search packet、可编辑 SVG/PDF 文本
和视觉 QA 记录。

## License / 许可证

MIT License. See [LICENSE](LICENSE).

采用 MIT License，详见 [LICENSE](LICENSE)。
