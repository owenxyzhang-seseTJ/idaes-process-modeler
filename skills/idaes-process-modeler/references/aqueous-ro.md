# Aqueous reverse osmosis / 水相反渗透

Use `assets/templates/seawater_ro.yaml` and `scripts/run_seawater_ro_demo.py`.
The general CLI supports `model_type: seawater_ro` with the reduced-order
reference backend; `solve_pyomo` provides a separate, custom equation model
on IDAES FlowsheetBlock, solved with IPOPT. It is not a WaterTAP unit model.

The gas-membrane partial-pressure law does not apply to dissolved salt.
Use solvent hydraulic pressure minus osmotic pressure, solute solution
diffusion, film concentration polarization, and axial component balances.
Keep engineering units explicit: m3/h, kg/m3, m2, bar, and m/h.

Source data: DuPont SW30HRLE-400 PDS 45-D00967-en Rev.8 (January 2026).
37 m2; 32000 ppm NaCl; 55 bar; 25 C; 8% recovery; 28.4 m3/day; 99.8%
nominal stabilized salt rejection. Record the PDF URL, page and hash.
The nominal point calibrates A and B conditional on assumed mass transfer,
osmotic coefficient and pressure drop. Fitting this point is not independent
physical validation. Manufacturer variation is not a statistical error bar.

Water and salt balances, positive states, zero DOF, IPOPT residuals,
30/60/120-cell convergence and comparison to the reference integration are
required. Report assumptions and pressure-exchanger energy scope explicitly.

This demo uses NaCl-equivalent seawater and fixed density. It does not resolve
boron, pH, ion-specific selectivity, nonideal activity, scaling or fouling.
Ion separation needs ionic composition and electroneutrality with appropriate
DSPM-DE, Nernst-Planck or aqueous ion-exchange constitutive equations.

水相反渗透应从本模板开始，不能复用气体膜的组分分压差模型。详细区分厂商标称数据、
条件标定参数和设计情景。当前 demo 只处理等效 NaCl 脱盐，不能报告 Li/Mg 等离子
选择性或饮水安全。完整图文报告位于 demo_results/seawater_ro/。
