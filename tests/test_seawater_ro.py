from pathlib import Path
import pytest
from idaes_process_modeler.models.seawater_ro import calibrate, parameters, simulate, local_flux
from idaes_process_modeler.spec import load_spec
from idaes_process_modeler.validation import validate_spec

SPEC = Path(__file__).resolve().parents[1]/'assets/templates/seawater_ro.yaml'


@pytest.fixture(scope='module')
def fitted():
    return calibrate(SPEC)


def test_nominal_calibration(fitted):
    a,b,s,_ = fitted
    assert a>0 and b>0
    assert s['permeate_m3_day'] == pytest.approx(28.4,rel=1e-6)
    assert s['rejection'] == pytest.approx(.998,abs=1e-8)


def test_conservation_and_pressure_response(fitted):
    a,b,_,_ = fitted
    p = parameters(SPEC)
    s,f = simulate(p,a,b)
    high,_ = simulate(dict(p,pressure_bar=65),a,b)
    assert abs(s['salt_balance_kg_h'])<1e-8
    assert abs(s['water_balance_kg_h'])<1e-7
    assert 0<s['recovery']<1
    assert high['recovery']>s['recovery']
    assert (f.surface_g_L>=f.bulk_g_L).all()
    assert (f.net_driving_bar>0).all()
    assert s['sec_pressure_exchanger_kWh_m3']<s['sec_no_erd_kWh_m3']


def test_salt_permeability_limit(fitted):
    a,b,_,_ = fitted
    p=parameters(SPEC)
    j,cp,cm=local_flux(32,60,a,b*1e-5,p)
    assert cp<1e-5
    assert j>0 and cm>32


@pytest.mark.parametrize('key,value',[('cells',0),('elements',1.5),('pump_efficiency',0),('pressure_bar',84),('temperature_K',310)])
def test_invalid_spec(key,value):
    spec=load_spec(SPEC)
    spec.data['parameters'][key]=value
    assert not validate_spec(spec).valid
