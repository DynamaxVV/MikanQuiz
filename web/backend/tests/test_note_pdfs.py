"""PDF attachment upload, download and portable note metadata."""
from dataclasses import replace
from pathlib import Path
from app.config import AppSettings
from app.models import FontReference
from app.services import images, sync
from tests.conftest import admin_headers

PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


def test_note_pdf_local_upload_download_and_config_roundtrip(client, tmp_path):
    client.app.state.settings = replace(client.app.state.settings, storage_backend="local", local_storage_path=str(tmp_path / "uploads"))
    headers = admin_headers(client)
    uploaded = client.post('/api/v1/admin/note-pdfs', headers=headers, files={'pdf': ('tutorial.pdf', PDF, 'application/pdf')})
    assert uploaded.status_code == 201, uploaded.text
    attachment = uploaded.json()
    assert attachment['pdf_name'] == 'tutorial.pdf'
    assert attachment['pdf_size_bytes'] == len(PDF)
    payload = {'sections': [{'name': '教程', 'sort_order': 0, 'cards': [{
        'title': '配图与 PDF', 'image_url': 'http://127.0.0.1:8000/uploads/cover.png',
        'note': '附完整教程', 'difficulty': 1, 'sort_order': 0, **attachment,
    }]}]}
    saved = client.put('/api/v1/admin/font-reference-sections', headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    card = saved.json()[0]['cards'][0]
    public = client.get('/api/v1/font-references').json()[0]['cards'][0]
    assert all(public[key] == value for key, value in attachment.items())
    download = client.get(f"/api/v1/font-references/{card['id']}/pdf")
    assert download.content == PDF
    assert download.headers['content-type'] == 'application/pdf'
    assert 'attachment;' in download.headers['content-disposition']
    assert 'tutorial.pdf' in download.headers['content-disposition']
    with client.app.state.database.sessions() as session:
        projection, _ = sync._notes_projection(session)
        assert projection[0]['cards'][0]['pdf_url'] == attachment['pdf_url']
    manifest = client.get('/api/v1/admin/config/export?scope=settings', headers=headers).json()
    exported = manifest['font_references']['sections'][0]['cards'][0]
    assert all(exported[key] == value for key, value in attachment.items())
    manifest['font_references']['sections'][0]['cards'][0]['pdf_name'] = 'updated.pdf'
    preview = client.post('/api/v1/admin/config/import/validate', headers=headers, json={'manifest': manifest, 'mode': 'settings'})
    assert preview.status_code == 200, preview.text
    hashes = preview.json()
    imported = client.post('/api/v1/admin/config/import', headers=headers, json={
        'manifest': manifest, 'mode': 'settings', 'confirm': True,
        'expected_current_hash': hashes['current_hash'], 'expected_incoming_hash': hashes['incoming_hash'],
    })
    assert imported.status_code == 200, imported.text
    assert client.get('/api/v1/font-references').json()[0]['cards'][0]['pdf_name'] == 'updated.pdf'
    with client.app.state.database.sessions() as session:
        stored = session.get(FontReference, card['id'])
        stored.pdf_url = client.app.state.settings.local_public_base_url + '/%2e%2e/private.pdf'
        session.commit()
    (tmp_path / 'private.pdf').write_bytes(PDF)
    assert client.get(f"/api/v1/font-references/{card['id']}/pdf").status_code == 404
    payload['sections'][0]['id'] = saved.json()[0]['id']
    payload['sections'][0]['cards'][0]['id'] = card['id']
    payload['sections'][0]['cards'][0].update(pdf_url=None, pdf_name='', pdf_size_bytes=0)
    removed = client.put('/api/v1/admin/font-reference-sections', headers=headers, json=payload)
    assert removed.status_code == 200, removed.text
    assert removed.json()[0]['cards'][0]['pdf_url'] is None
    assert client.get(f"/api/v1/font-references/{card['id']}/pdf").status_code == 404


def test_note_pdf_requires_admin_and_valid_file(client):
    assert client.post('/api/v1/admin/note-pdfs', files={'pdf': ('x.pdf', PDF, 'application/pdf')}).status_code == 401
    headers = admin_headers(client)
    for content, mime in [(b'not a PDF', 'application/pdf'), (PDF, 'image/png'), (b'%PDF-' + b'x' * images.MAX_PDF_BYTES, 'application/pdf')]:
        response = client.post('/api/v1/admin/note-pdfs', headers=headers, files={'pdf': ('x.pdf', content, mime)})
        assert response.status_code == 422
        assert response.json()['error']['code'] == 'INVALID_PDF'


def test_r2_pdf_sets_download_disposition(monkeypatch):
    captured = {}
    monkeypatch.setattr(images, 'ensure_configured', lambda *_: None)
    def upload(*args, **kwargs):
        captured.update(kwargs)
        assert Path(args[1]).read_bytes() == PDF
        return 'https://assets.example.test/notes-pdfs/tutorial.pdf'
    monkeypatch.setattr(images, 'run_uploader', upload)
    images.upload_pdf(AppSettings(), PDF, 'application/pdf', '嵌字教程.pdf')
    assert captured['key'].startswith('notes-pdfs/')
    assert captured['content_disposition'].startswith("attachment; filename*=UTF-8''")
    assert '%E5%B5%8C' in captured['content_disposition']
