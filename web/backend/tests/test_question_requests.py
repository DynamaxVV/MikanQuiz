"""Batch creation retries must never create a second question."""
from uuid import uuid4

from tests.conftest import admin_headers


def test_question_request_replay_conflict_and_deleted_question(client):
    headers = admin_headers(client)
    groups = client.get('/api/v1/admin/option-groups', headers=headers).json()
    groups[0]['options'] = [dict(name='合成字体', minimum_difficulty=2, sort_order=0)]
    groups = client.put('/api/v1/admin/option-groups', headers=headers, json={'groups': groups}).json()
    option = next(o for g in groups for o in g['options'])
    payload = dict(text='合成题图', image_url='https://example.test/crop.png',
                   difficulty=3, correct_option_id=option['id'], explanation='合成解析',
                   client_request_id=str(uuid4()))
    first = client.post('/api/v1/admin/questions', headers=headers, json=payload)
    assert first.status_code == 201, first.text
    replay = client.post('/api/v1/admin/questions', headers=headers, json=payload)
    assert replay.status_code == 201, replay.text
    assert replay.json()['id'] == first.json()['id']
    conflict = client.post('/api/v1/admin/questions', headers=headers,
                           json={**payload, 'explanation': '不同内容'})
    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'QUESTION_REQUEST_CONFLICT'
    question_id = first.json()['id']
    assert client.delete(f'/api/v1/admin/questions/{question_id}', headers=headers).status_code == 204
    deleted = client.post('/api/v1/admin/questions', headers=headers, json=payload)
    assert deleted.status_code == 409
    assert deleted.json()['error']['code'] == 'QUESTION_REQUEST_DELETED'
    assert client.get('/api/v1/admin/questions', headers=headers).json()['total'] == 0


def test_question_request_validation_and_auth(client):
    headers = admin_headers(client)
    groups = client.get('/api/v1/admin/option-groups', headers=headers).json()
    groups[0]['options'] = [dict(name='合成字体', minimum_difficulty=2, sort_order=0)]
    groups = client.put('/api/v1/admin/option-groups', headers=headers, json={'groups': groups}).json()
    option = next(o for g in groups for o in g['options'])
    payload = dict(text='测试', image_url='https://example.test/crop.png', difficulty=3,
                   correct_option_id=option['id'], explanation='解析', client_request_id=str(uuid4()))
    assert client.post('/api/v1/admin/questions', json=payload).status_code == 401
    invalid = client.post('/api/v1/admin/questions', headers=headers,
                          json={**payload, 'explanation': ' '})
    assert invalid.status_code == 422
    locked = client.post('/api/v1/admin/questions', headers=headers, json={**payload, 'difficulty': 1})
    assert locked.status_code == 422
    assert locked.json()['error']['code'] == 'FONT_OPTION_LOCKED'
    # A rejected request must not reserve the key or prevent a corrected retry.
    assert client.post('/api/v1/admin/questions', headers=headers, json=payload).status_code == 201
    assert client.post('/api/v1/admin/questions', headers=headers,
                       json={**payload, 'client_request_id': ''}).status_code == 422


def test_loopback_image_url_is_valid_for_local_storage(client):
    headers = admin_headers(client)
    groups = client.get('/api/v1/admin/option-groups', headers=headers).json()
    groups[0]['options'] = [dict(name='本地字体', minimum_difficulty=1, sort_order=0)]
    groups = client.put('/api/v1/admin/option-groups', headers=headers, json={'groups': groups}).json()
    option = next(o for g in groups for o in g['options'])
    response = client.post('/api/v1/admin/questions', headers=headers, json={
        'text': '本地存储题目', 'image_url': 'http://127.0.0.1:8001/uploads/crop.png',
        'difficulty': 1, 'correct_option_id': option['id'], 'explanation': '本地验收',
    })
    assert response.status_code == 201, response.text


def test_concurrent_question_request_and_account_isolation(client):
    from concurrent.futures import ThreadPoolExecutor
    from app.services.admin import add_admin

    headers = admin_headers(client)
    groups = client.get('/api/v1/admin/option-groups', headers=headers).json()
    groups[0]['options'] = [dict(name='并发字体', minimum_difficulty=1, sort_order=0)]
    groups = client.put('/api/v1/admin/option-groups', headers=headers, json={'groups': groups}).json()
    option = next(o for g in groups for o in g['options'])
    payload = dict(text='并发题图', image_url='https://example.test/crop.png', difficulty=1,
                   correct_option_id=option['id'], explanation='解析', client_request_id=str(uuid4()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post('/api/v1/admin/questions', headers=headers, json=payload), range(2)))
    assert all(response.status_code == 201 for response in responses)
    assert responses[0].json()['id'] == responses[1].json()['id']
    with client.app.state.database.sessions() as session:
        add_admin(session, 'second', 'another-password')
    token = client.post('/api/v1/admin/miniprogram/login', json={'username': 'second', 'password': 'another-password'}).json()['token']
    other = client.post('/api/v1/admin/questions', headers={'Authorization': f'Bearer {token}'}, json=payload)
    assert other.status_code == 201
    assert other.json()['id'] != responses[0].json()['id']
