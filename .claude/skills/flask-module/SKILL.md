---
name: flask-module
description: Buat modul atau endpoint baru di backend Flask ini (api/modules/<nama>) mengikuti pola endpoint → service → query. Pakai saat diminta membuat modul, endpoint, CRUD, atau fitur backend baru di proyek ini.
---

# flask-module

Aturan lengkap ada di `CLAUDE.md`, skema & permission di `SCHEMA.md`. Jangan baca modul lain sebagai contoh — template di bawah sudah cukup. Baca hanya tabel yang relevan di `SCHEMA.md`.

## Langkah

1. Buat `api/modules/<nama>/` berisi 5 file di bawah. Ganti `<nama>`, `<Nama>`, `<tabel>`, `<id>`.
2. Daftarkan di bagian `MODULES` paling bawah `api/__init__.py`:
   ```python
   from api.modules.<nama> import ns as <nama>_ns  # noqa: E402
   api.add_namespace(<nama>_ns, path="/<nama>")
   ```
3. Cek route terdaftar (output pendek, jangan cetak traceback penuh):
   ```bash
   venv/bin/python -c 'from api import app; print([r.rule for r in app.url_map.iter_rules() if "/<nama>" in r.rule])' 2>&1 | tail -3
   ```
4. Uji service dengan mock fungsi `query` — jangan tulis ke DB remote tanpa izin.

## Template

`__init__.py`
```python
# api/modules/<nama>/__init__.py
from flask_restx import Namespace

ns = Namespace("<nama>", description="<Nama> Module")

from . import endpoint  # noqa: E402,F401
```

`schema.py`
```python
# api/modules/<nama>/schema.py
from flask_restx import fields

from api.shared.docs import audit_fields
from . import ns

<nama>_input = ns.model("<Nama>Input", {
    "name": fields.String(required=True, min_length=1),
})

# output: didokumentasikan untuk OpenAPI/frontend (tidak mengubah respons)
<nama>_out = ns.model("<Nama>", {
    "<id>": fields.Integer(),
    "name": fields.String(),
    **audit_fields(),
})
```

`query.py` — SQL saja. Waktu selalu `get_wita()`, tulis pakai `begin()`.
```python
# api/modules/<nama>/query.py
from sqlalchemy import text

from api.core.database import get_engine
from api.utils.datetime import get_wita


def get_all():
    sql = text("SELECT * FROM <tabel> WHERE is_active = 1 ORDER BY <id>")
    with get_engine().connect() as conn:
        return conn.execute(sql).mappings().all()


def get_by_id(<id>):
    sql = text("SELECT * FROM <tabel> WHERE <id> = :<id>")
    with get_engine().connect() as conn:
        return conn.execute(sql, {"<id>": <id>}).mappings().first()


def insert(data, id_user):
    sql = text("""
        INSERT INTO <tabel> (name, created_at, created_by)
        VALUES (:name, :now, :id_user)
        RETURNING <id>
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "now": get_wita(), "id_user": id_user}).scalar()


def update(<id>, data, id_user):
    sql = text("""
        UPDATE <tabel> SET name = :name, updated_at = :now, updated_by = :id_user
        WHERE <id> = :<id>
    """)
    with get_engine().begin() as conn:
        return conn.execute(sql, {**data, "<id>": <id>, "now": get_wita(), "id_user": id_user}).rowcount
```

`service.py` — logika bisnis; gagal = `raise` turunan `AppError`.
```python
# api/modules/<nama>/service.py
from api.shared.exceptions import NotFoundError
from . import query


def list_all():
    return query.get_all()


def get(<id>):
    row = query.get_by_id(<id>)
    if not row:
        raise NotFoundError("<Nama> tidak ditemukan")
    return row


def create(data, id_user):
    return get(query.insert(data, id_user))


def update(<id>, data, id_user):
    if not query.update(<id>, data, id_user):
        raise NotFoundError("<Nama> tidak ditemukan")
    return get(<id>)
```

`endpoint.py` — HTTP saja. Lindungi dengan permission dari `SCHEMA.md`.
```python
# api/modules/<nama>/endpoint.py
from flask import request
from flask_jwt_extended import get_jwt_identity
from flask_restx import Resource

from api.core.security import permission_required
from api.shared.docs import api_doc
from api.shared.response import success
from api.utils.timing import measure_execution_time
from . import ns, service
from .schema import <nama>_input, <nama>_out


@ns.route("")
class <Nama>List(Resource):
    @api_doc(ns, <nama>_out, many=True)
    @permission_required("<nama>.manage")
    @measure_execution_time
    def get(self):
        """Akses: <nama>.manage. Daftar <nama>."""
        return success(service.list_all())

    @api_doc(ns, <nama>_out, status=201, errors=(400, 401, 403, 422))
    @ns.expect(<nama>_input, validate=True)
    @permission_required("<nama>.manage")
    @measure_execution_time
    def post(self):
        """Akses: <nama>.manage. Tambah <nama>."""
        data = service.create(request.get_json(), int(get_jwt_identity()))
        return success(data, "<Nama> berhasil ditambahkan", 201)


@ns.route("/<int:<id>>")
class <Nama>Detail(Resource):
    @api_doc(ns, <nama>_out, errors=(401, 403, 404))
    @permission_required("<nama>.manage")
    @measure_execution_time
    def get(self, <id>):
        """Akses: <nama>.manage. Detail <nama>."""
        return success(service.get(<id>))

    @api_doc(ns, <nama>_out, errors=(400, 401, 403, 404, 422))
    @ns.expect(<nama>_input, validate=True)
    @permission_required("<nama>.manage")
    @measure_execution_time
    def put(self, <id>):
        """Akses: <nama>.manage. Ubah <nama>."""
        data = service.update(<id>, request.get_json(), int(get_jwt_identity()))
        return success(data, "<Nama> berhasil diubah")
```

## Checklist sebelum selesai

- [ ] Tidak ada `now()` SQL / `datetime.now()` — semua waktu dari `get_wita()`
- [ ] Tidak ada `return error(...)` / `abort()` di endpoint — pakai `raise`
- [ ] Tidak import `query` modul lain
- [ ] Setiap endpoint punya `@permission_required` (kecuali memang publik)
- [ ] Hapus (soft delete) = `UPDATE ... SET is_active = 0`, bukan `DELETE` — kecuali tabel transaksi: `absensi_gagal` append-only; `absensi` hanya berubah lewat koreksi (upsert + `updated_by`), tidak pernah DELETE
- [ ] Setiap endpoint punya `@api_doc(...)` dengan model output (`@file_doc` untuk file)
- [ ] Namespace terdaftar di `api/__init__.py`
