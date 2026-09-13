# Method and provenance / 方法与来源记录

Status: READY_FOR_PREPROCESSING. The user directly authorized execution of this
demo and supplied the pressure, composition, gate, capacity, expansion, and
effective-heat basis.

状态：READY_FOR_PREPROCESSING。用户已直接授权运行该 demo，并给出了压力、组成、门控、
吸附量、膨胀和有效热参数。

Sources searched:

- User-provided operating specification in the conversation.
- Local `skills/idaes-process-modeler/references/psa.md` and
  `references/validation.md` for cycle metrics and evidence boundaries.
- SciPy `solve_ivp` documentation:
  <https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html>
  for the BDF implicit variable-order integration method.

检索来源：用户参数；本插件关于 PSA 循环和验证边界的本地参考；SciPy `solve_ivp` 官方
文档，用于 BDF 隐式变阶积分器的数值说明。

Chosen calculation method: a component-inventory, finite-conductance,
nonisothermal mixed-tank model. The raw machine-readable solver samples are
saved in each case `profiles.csv`; derived comparison values are saved in
`comparison.csv`. No smoothing, fitted measurement, or invented error bar is
applied.

选择的计算方法：组分库存 + 有限阀导纳 + 非等温全混罐模型。每个工况的原始求解采样保存在
`profiles.csv`，派生对比值保存在 `comparison.csv`。不进行平滑、不把模拟当拟合实验、也不
添加虚构误差棒。

Assumptions: 298 K reference state; STP = 273.15 K and 101325 Pa; isotropic
5% solid expansion; 10 um reference crystal length; 15 kJ mol^-1 diffusion
activation energy; 0.02/0.05 s^-1 CO2/N2 LDF coefficients; 0.1 s^-1 structural
relaxation; assumed heat capacities and UA; 40 kJ mol^-1 as one effective CO2
adsorption/structural heat magnitude; no measured hysteresis loop; no
competitive mixture fit; no vacuum-pump power calculation.

假设包括：298 K 参考状态；STP 为 273.15 K、101325 Pa；各向同性 5% 实体膨胀；10 um
参考晶体长度；15 kJ mol^-1 扩散活化能；CO2/N2 的 LDF 系数为 0.02/0.05 s^-1；结构响应
速率为 0.1 s^-1；热容和 UA 为假设值；40 kJ mol^-1 作为一次性的 CO2 吸附/结构有效热量；
没有实测滞后环、竞争吸附拟合和真空泵功耗计算。

Rejected alternatives: fixed 15% CO2 composition during evacuation; purge-gas
regeneration; counting gas initially present in the vessel as recovered solid
adsorbate; adding the 40 kJ mol^-1 value twice; calling CSS or balance closure
physical validation.

明确排除：抽气期间固定 15% CO2 组成；混合气吹扫再生；把容器初始气体当作固相捕集量；
重复加入 40 kJ mol^-1；把 CSS 或方程闭合称为物理验证。
