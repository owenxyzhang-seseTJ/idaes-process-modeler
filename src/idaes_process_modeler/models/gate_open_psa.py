"""Nonisothermal binary flexible-solid tank PSA, with component inventories.

This is a SciPy reduced-order model, not an IDAES unit model. Pressure follows
finite-conductance feed/exhaust valves rather than a prescribed gas composition.
STP: 273.15 K, 101325 Pa. Gas-accessible volume excludes the solid envelope;
adsorbed inventory is separate. Thermal closure is effective, not measured;
component equilibrium is not a competitive adsorption fit.
"""
import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from ..spec import load_spec
from ..units import si_value

R = 8.31446261815324
STP_CM3_PER_MOL = R * 273.15 / 101325 * 1e6
CM3_G_TO_MOL_KG = 1000 / STP_CM3_PER_MOL


def parameters(source):
    s = load_spec(source)
    def q(path, dim):
        return si_value(s.get(path), dim, field_name=path)
    p = dict(
        volume=q('material.initial_volume', 'volume'),
        density=q('material.density', 'mass_density'),
        temperature=q('feed.temperature', 'temperature'),
        high=q('feed.pressure', 'pressure'), low=q('cycle_settings.low_pressure', 'pressure'),
        flow=q('feed.molar_flow', 'molar_flow'),
        gate=q('material.gate_start', 'pressure'), width=q('material.gate_width', 'pressure'),
        anchor=q('material.low_anchor_pressure', 'pressure'),
        kf=q('material.gate_rate', 'rate_constant'),
        kc=q('material.co2_ldf', 'rate_constant'), kn=q('material.n2_ldf', 'rate_constant'),
        expansion=float(s.get('material.expansion_fraction')),
        void=float(s.get('bed.initial_void_fraction')),
        qlo=float(s.get('material.co2_low_cm3_stp_g')) * CM3_G_TO_MOL_KG,
        qhi=float(s.get('material.co2_high_cm3_stp_g')) * CM3_G_TO_MOL_KG,
        qn=float(s.get('material.n2_cm3_stp_g')) * CM3_G_TO_MOL_KG,
        valve=float(s.get('numerics.valve_conductance_mol_s_pa')),
        crystal=q('material.crystal_length', 'length'),
        ea=q('material.diffusion_activation_energy', 'energy_per_mol'),
        heat=q('thermal.effective_binding_energy', 'energy_per_mol'),
        cp=float(s.get('thermal.solid_heat_capacity_j_kg_k')),
        wall=float(s.get('thermal.wall_heat_capacity_j_k')),
        cv=float(s.get('thermal.gas_cv_j_mol_k')),
        ua=float(s.get('thermal.ua_w_k')),
        ambient=q('thermal.ambient_temperature', 'temperature'),
    )
    if not all(np.isfinite(v) and v > 0 for k, v in p.items() if k != 'expansion'):
        raise ValueError('all dimensional parameters and capacities must be finite and positive')
    if not 0 < p['void'] < 1 or not 0 <= p['expansion'] < p['void'] / (1-p['void']):
        raise ValueError('expansion must leave a positive gas void in the rigid vessel')
    if not 0 < p['low'] <= p['high'] or p['qhi'] <= p['qlo']:
        raise ValueError('require low <= high pressure and high > low CO2 capacity')
    if s.components != ['CO2', 'N2']:
        raise ValueError('gate model requires components [CO2, N2]')
    p['y'] = np.array([float(s.get('feed.composition.CO2')), float(s.get('feed.composition.N2'))])
    if np.any(p['y'] <= 0) or not np.isclose(p['y'].sum(), 1):
        raise ValueError('feed fractions must be positive and sum to one')
    p['temperature_shift'] = bool(s.get('thermal.gate_temperature_shift', True))
    p['mass'] = p['volume'] * p['density']
    # Convert effective adsorption enthalpy magnitude to binding internal energy
    # at the reference temperature, neglecting solid pV and adsorbate volume.
    p['binding'] = p['heat'] - R*p['temperature']
    p['vessel'] = p['volume'] / (1-p['void'])
    p['steps'] = [(x['name'], si_value(x['duration'], 'time')) for x in s.get('cycle')]
    if [x[0] for x in p['steps']] != ['adsorption', 'evacuation'] or any(x[1] <= 0 for x in p['steps']):
        raise ValueError('cycle requires positive-duration adsorption, evacuation')
    return s, p


def equilibrium(partial, fraction, p):
    """A reversible 10–11 kPa gate, with a low-pressure Henry continuation."""
    base = p['qlo'] * np.clip(partial[0] / p['anchor'], 0, 1)
    return np.array([base + (p['qhi']-p['qlo']) * fraction,
                     p['qn'] * np.clip(partial[1]/p['anchor'], 0, 1)])


def run_gate_open(source, *, backend='reduced_order'):
    if backend != 'reduced_order':
        raise ValueError('gate_open_psa currently supports only the explicit reduced_order backend')
    s, p = parameters(source)
    rtol = float(s.get('numerics.rtol', 1e-7))
    atol = float(s.get('numerics.atol', 1e-10))
    maxstep = si_value(s.get('numerics.max_step'), 'time')
    interval = si_value(s.get('numerics.output_interval'), 'time')
    maxcycles = int(s.get('cycle_settings.max_cycles'))
    tolerance = float(s.get('cycle_settings.css_tolerance'))
    if min(rtol, atol, maxstep, interval, maxcycles, tolerance) <= 0:
        raise ValueError('numerical settings must be positive')
    # State: gas moles (2), adsorbed loading (2), open fraction, inlet (2), outlet (2).
    # Extra states: bed temperature, integrated external energy input.
    state = np.zeros(11)
    state[9] = p['temperature']
    state[:2] = p['low']*(p['vessel']-p['volume'])/(R*p['temperature'])*p['y']
    state[2:4] = equilibrium(p['low']*p['y'], 0, p)
    rows, streams, metrics = [], [], []
    previous = None
    clock = 0.
    def observe(z):
        gas = np.maximum(z[:2], 1e-20)
        vg = p['vessel'] - p['volume']*(1+p['expansion']*z[4])
        return gas/gas.sum(), gas*R*z[9]/vg
    def rhs(kind, z):
        y, partial = observe(z)
        pressure = partial.sum()
        temp = z[9]
        shift = np.exp(np.clip(p['heat']/R*(1/p['temperature']-1/temp), -30, 30)) if p['temperature_shift'] else 1.
        effective_partial = partial/shift
        fstar = np.clip((effective_partial[0]-p['gate'])/p['width'], 0, 1)
        df = p['kf']*(fstar-z[4])
        length_factor = (1+p['expansion']*z[4])**(1/3)
        kinetic_factor = np.exp(np.clip(-p['ea']/R*(1/temp-1/p['temperature']), -30, 30))/length_factor**2
        dq = np.array([p['kc'], p['kn']])*kinetic_factor*(equilibrium(effective_partial, z[4], p)-z[2:4])
        target = p['low'] if kind == 'evacuation' else p['high']
        fin = 0. if kind == 'evacuation' else p['valve']*max(target-pressure, 0.)
        if kind == 'adsorption':
            fin += p['flow']
        fout = p['valve']*max(pressure-target, 0.)
        incoming, outgoing = fin*p['y'], fout*y
        dn = incoming-outgoing-p['mass']*dq
        # Rigid control volume: solid/gas mechanical work is internal, not added twice.
        # U=(m*cp+Cwall+n*Cv)*T - m*Ebind*qCO2, with constant effective capacities.
        power = fin*(p['cv']+R)*p['temperature']-fout*(p['cv']+R)*temp-p['ua']*(temp-p['ambient'])
        capacity = p['mass']*p['cp']+p['wall']+sum(z[:2])*p['cv']
        dtemp = (power+p['mass']*p['binding']*dq[0]-p['cv']*temp*sum(dn))/capacity
        return np.r_[dn, dq, df, incoming, outgoing, dtemp, power]
    for cycle in range(1, maxcycles+1):
        start = state.copy()
        q_extrema = []
        product = np.zeros(2)
        for kind, duration in p['steps']:
            before = state.copy()
            times = np.linspace(0, duration, int(np.ceil(duration/interval))+1)
            sol = solve_ivp(lambda t, z: rhs(kind, z), (0, duration), state,
                            method='BDF', rtol=rtol, atol=atol, max_step=maxstep, t_eval=times)
            if not sol.success:
                raise RuntimeError(sol.message)
            if np.min(sol.y[:4]) < -1e-7 or np.min(sol.y[4]) < -1e-7 or np.max(sol.y[4]) > 1+1e-7:
                raise RuntimeError('unphysical state produced')
            state = sol.y[:, -1]
            amount_in, amount_out = state[5:7]-before[5:7], state[7:9]-before[7:9]
            if kind == 'evacuation':
                product = amount_out
            for t, z in zip(sol.t, sol.y.T):
                y, part = observe(z)
                dz = rhs(kind, z)
                rows.append(dict(cycle=cycle, step=kind, time_s=clock+t,
                    pressure_kpa=part.sum()/1000, co2_partial_kpa=part[0]/1000,
                    co2_mole_fraction=y[0], co2_loading_cm3_stp_g=z[2]/CM3_G_TO_MOL_KG,
                    n2_loading_cm3_stp_g=z[3]/CM3_G_TO_MOL_KG, open_fraction=z[4],
                    solid_volume_l=p['volume']*(1+p['expansion']*z[4])*1000, temperature_k=z[9],
                    crystal_length_um=p['crystal']*(1+p['expansion']*z[4])**(1/3)*1e6,
                    co2_k_eff_s=p['kc']*np.exp(-p['ea']/R*(1/z[9]-1/p['temperature']))/(1+p['expansion']*z[4])**(2/3),
                    co2_rate_cm3_stp_g_s=dz[2]/CM3_G_TO_MOL_KG))
            q_extrema.extend(sol.y[2])
            streams.append(dict(cycle=cycle, step=kind, co2_in_mol=amount_in[0], n2_in_mol=amount_in[1],
                co2_out_mol=amount_out[0], n2_out_mol=amount_out[1]))
            clock += duration
        feed = state[5:7]-start[5:7]
        out = state[7:9]-start[7:9]
        inventory_change = state[:2]-start[:2]+p['mass']*(state[2:4]-start[2:4])
        closure = np.max(np.abs(feed-out-inventory_change))
        scale = np.r_[np.maximum(np.abs(state[:2]), .01), [p['qhi'], p['qn']], 1.]
        physical = np.r_[state[:5], state[9]]
        scale = np.r_[scale, p['temperature']]
        delta = float(np.max(np.abs(physical-previous)/scale)) if previous is not None else None
        def energy(z):
            return (p['mass']*p['cp']+p['wall']+sum(z[:2])*p['cv'])*z[9]-p['mass']*p['binding']*z[2]
        energy_error = energy(state)-energy(start)-(state[10]-start[10])
        net = product[0]
        metrics.append(dict(cycle=cycle, purity=float(product[0]/max(product.sum(), 1e-30)),
            recovery=float(net/max(feed[0], 1e-30)), co2_product_mol=product[0],
            net_co2_released_mol=net, feed_co2_in_mol=feed[0], energy_balance_error_j=energy_error,
            working_capacity_cm3_stp_g=(max(q_extrema)-min(q_extrema))/CM3_G_TO_MOL_KG,
            mass_balance_error_mol=closure, css_state_delta=delta,
            end_co2_partial_kpa=observe(state)[1][0]/1000, end_open_fraction=state[4]))
        previous = physical.copy()
        if delta is not None and delta < tolerance:
            break
    final = metrics[-1]
    summary = dict(model_type='gate_open_psa', backend=backend,
        solver={'termination': 'success', 'method': 'SciPy BDF', 'rtol': rtol, 'atol': atol, 'max_step_s': maxstep},
        components=s.components, solid_mass_kg=p['mass'], vessel_volume_l=p['vessel']*1000,
        equilibrium_working_capacity_mol=p['mass']*(p['qhi']-p['qlo']),
        css_converged=bool(final['css_state_delta'] is not None and final['css_state_delta'] < tolerance),
        cycles_run=cycle, mass_balance_error=max(m['mass_balance_error_mol'] for m in metrics),
        **{k:v for k,v in final.items() if k != 'cycle'},
        assumptions=s.get('provenance.assumptions'),
        warnings=['Numerical scenario, not experimental validation or an IDAES unit model.',
                  'Valve pressure targets are approximate; inspect actual pressure profiles.',
                  'Effective thermal closure; no measured hysteresis, axial gradients, pump energy or competitive fit.'])
    return dict(summary=summary, profiles=pd.DataFrame(rows), streams=pd.DataFrame(streams),
                metrics=pd.DataFrame(metrics), convergence={'records': metrics}, figure_data={})
