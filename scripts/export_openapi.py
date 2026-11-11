"""Ekspor spec OpenAPI (Swagger 2.0) dari flask-restx ke docs/openapi.json.

Pakai:
    venv/bin/python scripts/export_openapi.py           # tulis file
    venv/bin/python scripts/export_openapi.py --check   # exit 1 jika file basi (untuk CI / sebelum commit)

Tidak menyentuh database. Butuh .env (JWT_SECRET_KEY) karena app di-import.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from api import api, app  # noqa: E402

OUT = os.path.join(ROOT, "docs", "openapi.json")


def build():
    with app.test_request_context():
        spec = json.loads(json.dumps(api.__schema__))
    spec.pop("host", None)  # host diatur frontend (baseURL per environment), bukan dikunci di spec
    # urutan stabil: diff git hanya menampilkan perubahan API yang nyata
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main():
    content = build()
    if "--check" in sys.argv:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != content:
            print("docs/openapi.json basi. Jalankan: venv/bin/python scripts/export_openapi.py")
            sys.exit(1)
        print("docs/openapi.json up to date")
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(content)
    spec = json.loads(content)
    ops = sum(1 for p in spec["paths"].values() for m in p if m != "parameters")
    print(f"Ditulis {os.path.relpath(OUT, ROOT)}: {len(spec['paths'])} path, {ops} operasi, "
          f"{len(spec['definitions'])} model")


if __name__ == "__main__":
    main()
