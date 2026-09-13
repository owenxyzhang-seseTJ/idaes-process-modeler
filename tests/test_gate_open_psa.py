from pathlib import Path
import numpy as np
import pytest
from idaes_process_modeler.models.gate_open_psa import parameters, equilibrium, run_gate_open, CM3_G_TO_MOL_KG

TEMPLATE = Path(__file__).resolve().parents[1] / 'assets/templates/gate_open_psa.yaml'


def test_user_anchors_and_volume():
    s, p = parameters(TEMPLATE)
    assert p['mass'] == pytest.approx(1.5)
    assert p['volume']*(1+p['expansion'])*1000 == pytest.approx(1.05)
    for pressure, expected in [(5000, 1), (10000, 1), (10500, 20.5), (11000, 40), (15000, 40)]:
        f = np.clip((pressure-p['gate'])/p['width'], 0, 1)
        result = equilibrium(np.array([pressure, 85000]), f, p)/CM3_G_TO_MOL_KG
        assert result == pytest.approx([expected, 1])
    assert p['mass']*(p['qhi']-p['qlo']) == pytest.approx(2.60997945422)


def test_cycle_conservation_and_vacuum_accounting():
    r = run_gate_open(TEMPLATE)
    a = r['summary']
    assert a['css_converged']
    assert a['mass_balance_error'] < 1e-7
    assert a['co2_product_mol'] == pytest.approx(a['net_co2_released_mol'])
    assert a['net_co2_released_mol']/a['feed_co2_in_mol'] == pytest.approx(a['recovery'])
    assert 0 < a['working_capacity_cm3_stp_g'] < 40
    assert abs(a['energy_balance_error_j']) < 1
    assert a['end_open_fraction'] < .001
    frame = r['profiles']
    assert frame['solid_volume_l'].between(1-1e-7, 1.05+1e-7).all()
    assert frame['co2_mole_fraction'].between(0, 1).all()
    assert frame['temperature_k'].between(200, 400).all()
    assert frame['crystal_length_um'].between(10-1e-6, 10*1.05**(1/3)+1e-6).all()
    with pytest.raises(ValueError):
        run_gate_open(TEMPLATE, backend='idaes')


def test_invalid_expansion_rejected():
    s, _ = parameters(TEMPLATE)
    s.data['material']['expansion_fraction'] = 1
    with pytest.raises(ValueError):
        parameters(s)
