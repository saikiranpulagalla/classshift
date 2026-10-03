from __future__ import annotations

import pytest

from app import create_app
from classshift.solution_validator import ValidationResult

@pytest.fixture
def client():
    app=create_app(); app.config.update(TESTING=True); return app.test_client()


def test_demo(client):
    r=client.get('/api/demo'); assert r.status_code==200; assert 'lessons' in r.get_json()


def test_valid_optimal(client):
    r=client.post('/api/recover',json={'outages':[{'room_id':'LAB_A','period_ids':['MON_P3']}]}); body=r.get_json(); assert r.status_code==200 and body['status']=='OPTIMAL' and body['validated'] is True and body['move_count']==3


def test_valid_infeasible(client):
    r=client.post('/api/recover',json={'outages':[{'room_id':'LAB_A','period_ids':['MON_P3']},{'room_id':'LAB_B','period_ids':['MON_P3']},{'room_id':'LAB_C','period_ids':['MON_P3']}]}); assert r.status_code==200 and r.get_json()['status']=='INFEASIBLE'


def test_wrong_content_type(client):
    r=client.post('/api/recover',data='{}',content_type='text/plain'); assert r.status_code==400 and r.get_json()['status']=='INVALID_INPUT'


def test_malformed_json(client):
    r=client.post('/api/recover',data='{',content_type='application/json'); assert r.status_code==400 and r.get_json()['status']=='INVALID_INPUT'


def test_invalid_outage(client):
    r=client.post('/api/recover',json={'outages':[{'room_id':'NOPE','period_ids':['MON_P3']}]}); assert r.status_code==400 and r.get_json()['status']=='INVALID_INPUT'


def test_internal_exception_maps_to_internal_error(monkeypatch, client):
    monkeypatch.setattr('app.load_dataset', lambda *_: (_ for _ in ()).throw(RuntimeError('boom')))
    r=client.post('/api/recover',json={'outages':[]}); assert r.status_code==500 and r.get_json()['status']=='INTERNAL_ERROR'


def test_validator_failure_never_returns_success(monkeypatch, client):
    monkeypatch.setattr('classshift.service.validate_solution', lambda *a,**k: ValidationResult(False,('bad',),None))
    r=client.post('/api/recover',json={'outages':[{'room_id':'LAB_A','period_ids':['MON_P3']}]}); body=r.get_json(); assert r.status_code==500 and body['status']=='VALIDATOR_FAILURE' and body['validated'] is False


def test_unexpected_request_field_is_invalid(client):
    r=client.post('/api/recover',json={'outages':[],'extra':True})
    assert r.status_code==400 and r.get_json()['status']=='INVALID_INPUT'


def test_request_size_limit(client):
    payload='{"outages":[],"padding":"' + ('x' * (129 * 1024)) + '"}'
    r=client.post('/api/recover',data=payload,content_type='application/json')
    assert r.status_code==413 and r.get_json()['status']=='INVALID_INPUT'
