"""Isothermal aqueous NaCl RO: solution diffusion + film polarization.

Engineering units: m3/h, kg/m3, bar, m2; J, B, k in m/h; A in m/h/bar.
Custom Pyomo equations on an IDAES FlowsheetBlock, not a WaterTAP unit.
"""
from pathlib import Path
import math

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from scipy.optimize import brentq, least_squares

from ..spec import load_spec


def parameters(source):
    spec = load_spec(source)
    if spec.components != ['H2O', 'NaCl']:
        raise ValueError('components must be [H2O, NaCl]')
    p = dict(spec.get('parameters', {}))
    positive = ('temperature_K', 'feed_salt_kg_m3', 'feed_flow_m3_h',
                'pressure_bar', 'element_area_m2', 'elements',
                'mass_transfer_m_h', 'osmotic_coefficient', 'cells')
    for key in positive:
        if not math.isfinite(float(p[key])) or p[key] <= 0:
            raise ValueError(f'{key} must be positive and finite')
    for key in ('permeate_pressure_bar', 'pressure_drop_bar_per_element'):
        if not math.isfinite(float(p[key])) or p[key] < 0:
            raise ValueError(f'{key} must be nonnegative and finite')
    for key in ('pump_efficiency', 'energy_recovery_efficiency'):
        if not math.isfinite(float(p[key])) or not 0 < p[key] <= 1:
            raise ValueError(f'{key} must be in (0,1]')
    for key in ('elements', 'cells'):
        if p[key] != int(p[key]):
            raise ValueError(f'{key} must be an integer')
    if p['temperature_K'] != 298.15:
        raise ValueError('Calibration is restricted to 298.15 K; no temperature correction fitted')
    if p['pressure_bar'] > 83:
        raise ValueError('Exceeds manufacturer maximum pressure of 83 bar')
    if p['pressure_drop_bar_per_element'] > 1 or p['pressure_drop_bar_per_element']*p['elements'] > 3.5:
        raise ValueError('Exceeds manufacturer element/vessel pressure-drop limit')
    if p['pressure_bar']-p['permeate_pressure_bar'] <= p['elements']*p['pressure_drop_bar_per_element']:
        raise ValueError('Retentate pressure must exceed permeate pressure')
    return p


def osmotic_slope(p):
    # NaCl dissociation factor 2; MW kg/mol; Pa converted to bar.
    return 2*p['osmotic_coefficient']*8.314462618*p['temperature_K']/0.05844277/1e5


def local_flux(c, pressure, A, B, p):
    """Solve J=A(dP-dPi), Cp=B Cm/(J+B), film Cp+(Cb-Cp)exp(J/k)."""
    dp = pressure-p['permeate_pressure_bar']
    if min(c, dp, A, B) <= 0:
        raise ValueError('Positive concentration, pressure driving force and permeabilities required')
    k, alpha = p['mass_transfer_m_h'], osmotic_slope(p)

    def state(j):
        e = math.exp(j/k)
        cp = B*c*e/(j+B*e)
        cm = cp+(c-cp)*e
        return cp, cm

    def residual(j):
        cp, cm = state(j)
        return j-A*(dp-alpha*(cm-cp))

    j = brentq(residual, 0., A*dp, xtol=1e-13)
    cp, cm = state(j)
    return j, cp, cm


def summarize(frame, p):
    qf, cf = p['feed_flow_m3_h'], p['feed_salt_kg_m3']
    qr, sr = frame.iloc[-1][['flow_m3_h', 'salt_kg_h']]
    qp, sp = frame.iloc[-1][['permeate_m3_h', 'permeate_salt_kg_h']]
    cp = sp/qp
    pb = frame.iloc[-1].pressure_bar
    salt_error = qf*cf-qr*(sr/qr)-sp
    water_error = (1000-cf)*qf-(1000*qr-sr)-(1000*qp-sp)
    sec = p['pressure_bar']*qf/(36*p['pump_efficiency']*qp)
    sec_erd = (p['pressure_bar']*qf-p['energy_recovery_efficiency']*pb*qr)/(36*p['pump_efficiency']*qp)
    return dict(permeate_m3_day=float(qp*24), recovery=float(qp/qf),
                permeate_mg_L=float(cp*1000), brine_g_L=float(sr/qr),
                rejection=float(1-cp/cf), sec_no_erd_kWh_m3=float(sec),
                sec_pressure_exchanger_kWh_m3=float(sec_erd),
                salt_balance_kg_h=float(salt_error), water_balance_kg_h=float(water_error),
                volume_balance_m3_h=float(qf-qr-qp),
                feed_osmotic_bar=float(osmotic_slope(p)*cf))


def simulate(p, A, B, rtol=1e-8):
    area = p['elements']*p['element_area_m2']
    qf, cf = p['feed_flow_m3_h'], p['feed_salt_kg_m3']

    def rhs(a, y):
        if y[0] <= 0 or y[1] <= 0:
            raise ValueError('Nonpositive retentate inventory')
        pressure = p['pressure_bar']-p['pressure_drop_bar_per_element']*a/p['element_area_m2']
        j, cp, _ = local_flux(y[1]/y[0], pressure, A, B, p)
        return [-j, -j*cp, j, j*cp]

    sol = solve_ivp(rhs, (0, area), [qf, qf*cf, 0., 0.], method='DOP853',
                    rtol=rtol, atol=rtol*1e-3, dense_output=True)
    if not sol.success:
        raise RuntimeError(sol.message)
    rows = []
    for a, y in zip(np.linspace(0, area, p['cells']+1), sol.sol(np.linspace(0, area, p['cells']+1)).T):
        pressure = p['pressure_bar']-p['pressure_drop_bar_per_element']*a/p['element_area_m2']
        j, cp, cm = local_flux(y[1]/y[0], pressure, A, B, p)
        rows.append(dict(area_m2=a, flow_m3_h=y[0], salt_kg_h=y[1],
                         permeate_m3_h=y[2], permeate_salt_kg_h=y[3],
                         bulk_g_L=y[1]/y[0], surface_g_L=cm,
                         local_permeate_mg_L=cp*1000, flux_L_m2_h=j*1000,
                         pressure_bar=pressure, net_driving_bar=pressure-p['permeate_pressure_bar']-osmotic_slope(p)*(cm-cp)))
    frame = pd.DataFrame(rows)
    return summarize(frame, p), frame


def calibrate(source):
    spec = load_spec(source)
    p, d = parameters(spec), spec.get('calibration')
    p.update(elements=1, pressure_bar=d['pressure_bar'],
             feed_salt_kg_m3=d['feed_salt_kg_m3'], element_area_m2=d['element_area_m2'],
             feed_flow_m3_h=d['permeate_m3_day']/24/d['recovery'])
    target_cp = d['feed_salt_kg_m3']*(1-d['rejection'])*1000

    def residual(x):
        s, _ = simulate(p, *np.exp(x))
        return [math.log(s['permeate_m3_day']/d['permeate_m3_day']),
                math.log(s['permeate_mg_L']/target_cp)]

    fit = least_squares(residual, np.log([0.0012, 0.00005]),
                        bounds=(np.log([1e-5,1e-8]),np.log([.01,.01])),
                        xtol=1e-11, ftol=1e-11, gtol=1e-11)
    if not fit.success or max(abs(fit.fun)) > 1e-6:
        raise RuntimeError('Manufacturer calibration failed')
    A, B = np.exp(fit.x)
    result, frame = simulate(p, A, B)
    return float(A), float(B), result, frame


def solve_pyomo(p, A, B, log_path=None):
    """Independent implicit-midpoint discretization with IPOPT and IDAES DOF audit."""
    import idaes
    import pyomo.environ as pe
    from idaes.core import FlowsheetBlock
    from idaes.core.util.model_statistics import degrees_of_freedom

    n = p['cells']
    da = p['elements']*p['element_area_m2']/n
    _, init = simulate(p, A, B)
    m = pe.ConcreteModel()
    m.fs = FlowsheetBlock(dynamic=False)
    f = m.fs
    f.nodes, f.cells = pe.RangeSet(0,n), pe.RangeSet(1,n)
    f.q = pe.Var(f.nodes, bounds=(1e-6,None), initialize=lambda _,i: init.iloc[i].flow_m3_h)
    f.s = pe.Var(f.nodes, bounds=(1e-8,None), initialize=lambda _,i: init.iloc[i].salt_kg_h)
    f.j = pe.Var(f.cells, bounds=(1e-10,None), initialize=lambda _,i: init.iloc[i].flux_L_m2_h/1000)
    f.cp = pe.Var(f.cells, bounds=(1e-10,None), initialize=lambda _,i: init.iloc[i].local_permeate_mg_L/1000)
    f.cm = pe.Var(f.cells, bounds=(1e-10,None), initialize=lambda _,i: init.iloc[i].surface_g_L)
    f.q[0].fix(p['feed_flow_m3_h'])
    f.s[0].fix(p['feed_flow_m3_h']*p['feed_salt_kg_m3'])
    f.volume = pe.Constraint(f.cells, rule=lambda _,i: f.q[i]-f.q[i-1]+da*f.j[i]==0)
    f.salt = pe.Constraint(f.cells, rule=lambda _,i: f.s[i]-f.s[i-1]+da*f.j[i]*f.cp[i]==0)
    f.film = pe.Constraint(f.cells, rule=lambda _,i: f.cm[i]==f.cp[i]+((f.s[i]+f.s[i-1])/(f.q[i]+f.q[i-1])-f.cp[i])*pe.exp(f.j[i]/p['mass_transfer_m_h']))
    f.water_flux = pe.Constraint(f.cells, rule=lambda _,i: f.j[i]/A==p['pressure_bar']-p['pressure_drop_bar_per_element']*(i-.5)*da/p['element_area_m2']-p['permeate_pressure_bar']-osmotic_slope(p)*(f.cm[i]-f.cp[i]))
    f.salt_flux = pe.Constraint(f.cells, rule=lambda _,i: f.j[i]*f.cp[i]/B==f.cm[i]-f.cp[i])
    dof = degrees_of_freedom(m)
    if dof != 0:
        raise RuntimeError(f'Expected zero DOF, got {dof}')
    m.obj = pe.Objective(expr=0)
    solver = pe.SolverFactory('ipopt', executable=str(Path(idaes.bin_directory)/'ipopt'))
    solver.options.update({'tol':1e-9, 'max_iter':1000})
    result = solver.solve(m, tee=False, **({'logfile':str(log_path)} if log_path else {}))
    if not pe.check_optimal_termination(result):
        raise RuntimeError(str(result.solver))
    residual = max(abs(pe.value(c.body-c.lower)) for c in m.component_data_objects(pe.Constraint,active=True))
    qp = p['feed_flow_m3_h']-pe.value(f.q[n])
    sp = p['feed_flow_m3_h']*p['feed_salt_kg_m3']-pe.value(f.s[n])
    return dict(backend='custom Pyomo equations on IDAES FlowsheetBlock',
                solver='IPOPT', termination=str(result.solver.termination_condition),
                dof=dof, cells=n, max_equation_residual_engineering_units=residual,
                permeate_m3_day=qp*24, permeate_mg_L=sp/qp*1000,
                recovery=qp/p['feed_flow_m3_h'])


def run_ro(source, backend='reduced_order'):
    if backend != 'reduced_order':
        raise ValueError('Use solve_pyomo for the explicit IDAES/Pyomo model')
    p = parameters(source)
    A, B, cal, _ = calibrate(source)
    summary, frame = simulate(p, A, B)
    summary.update(model_type='seawater_ro', backend='SciPy DOP853 aqueous solution-diffusion',
                   solver={'termination':'success'}, calibration=cal,
                   A_m_h_bar=A, B_m_h=B,
                   mass_balance_error=max(abs(summary['salt_balance_kg_h'])/(p['feed_flow_m3_h']*p['feed_salt_kg_m3']),abs(summary['water_balance_kg_h'])/(1000*p['feed_flow_m3_h'])),
                   warnings=['Manufacturer nominal calibration, not independent experimental validation',
                             'NaCl equivalent, constant density and osmotic coefficient; no boron/ion selectivity'])
    last = frame.iloc[-1]
    streams = pd.DataFrame([
        dict(stream='feed',flow_m3_h=p['feed_flow_m3_h'],salt_kg_h=p['feed_flow_m3_h']*p['feed_salt_kg_m3']),
        dict(stream='brine',flow_m3_h=last.flow_m3_h,salt_kg_h=last.salt_kg_h),
        dict(stream='permeate',flow_m3_h=last.permeate_m3_h,salt_kg_h=last.permeate_salt_kg_h)])
    streams['water_kg_h'] = 1000*streams.flow_m3_h-streams.salt_kg_h
    return dict(summary=summary, profiles=frame, streams=streams,
                metrics=pd.DataFrame([dict(metric=k,value=v) for k,v in summary.items() if isinstance(v,(float,int))]),
                convergence={'method':'DOP853','rtol':1e-8,'atol':1e-11,'success':True})
