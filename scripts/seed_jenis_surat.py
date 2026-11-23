"""Generator migrations/011_seed_jenis_surat.sql: jenis surat yang sering dibuat (contoh format surat desa,
Perbup tata naskah dinas) + daftar surat keterangan desa. Skema & redaksi divalidasi dengan service asli
(validate_skema, clean_template) supaya seed pasti bisa dibuka di wizard.
Pakai: venv/bin/python scripts/seed_jenis_surat.py  (lalu commit file migrasinya)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.modules.jenis_surat import service  # noqa: E402
from api.utils.template import sanitize_html  # noqa: E402

OUT = ROOT / "migrations" / "011_seed_jenis_surat.sql"

# ------------------------------------------------------------------ potongan redaksi
YBT = ('<p style="text-indent: 0">Yang bertanda tangan di bawah ini:</p>'
       '<table><tbody><tr><td style="width: 40mm">Nama</td><td>:</td><td>{{ ttd.nama }}</td></tr>'
       '<tr><td>Jabatan</td><td>:</td><td>{{ ttd.jabatan }}</td></tr></tbody></table>'
       '<p style="text-indent: 0">dengan ini menerangkan bahwa:</p>')
PENDUDUK = ("<p>Orang tersebut di atas benar-benar penduduk Desa {{ desa.nama }} Kecamatan {{ desa.kecamatan }} "
            "Kabupaten {{ desa.kabupaten }}.</p>")
KEPERLUAN = '<p>Surat keterangan ini dipergunakan untuk keperluan: <b>"{{ keperluan }}"</b>.</p>'
DEMIKIAN = "<p>Demikian surat keterangan ini dibuat untuk dipergunakan sebagaimana mestinya.</p>"
DEMIKIAN_SB = "<p>Demikian disampaikan, atas perhatiannya diucapkan terima kasih.</p>"


def baris(*pasangan):
    """Tabel label : nilai tanpa garis (style .isi table)."""
    rows = "".join(f'<tr><td style="width: 50mm">{a}</td><td>:</td><td>{b}</td></tr>' for a, b in pasangan)
    return f"<table><tbody>{rows}</tbody></table>"


# ------------------------------------------------------------------ potongan skema
def orang(key="pemohon", label="Data Pemohon", tampilkan=None):
    s = {"key": key, "label": label, "type": "penduduk"}
    s["tampilkan"] = tampilkan or ["nama", "nik", "ttl", "jenis_kelamin", "agama", "status_perkawinan", "pekerjaan",
                                   "alamat"]
    return s


def f(key, label, type="text", required=False, register=False, **x):
    return {"key": key, "label": label, "type": type, **({"required": True} if required else {}),
            **({"register": True} if register else {}), **x}


def isian(key, label, *fields):
    return {"key": key, "label": label, "type": "fields", "fields": list(fields)}


KEP = f("keperluan", "Keperluan", required=True, register=True)
KEPALA_DINAS = isian("kepala_surat", "Kepala Surat",
                     f("sifat", "Sifat", "select", options=["Biasa", "Penting", "Segera", "Rahasia"]),
                     f("lampiran", "Lampiran"),
                     f("perihal", "Perihal", required=True, register=True),
                     f("kepada", "Kepada Yth.", required=True, register=True),
                     f("di_tempat", "Di (tempat tujuan)"),
                     f("tembusan", "Tembusan (satu per baris)", "textarea"))
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

# (code, name, kode_klasifikasi, skema, redaksi, persyaratan)
KTP_KK = [{"nama": "KTP", "wajib": 1}, {"nama": "Kartu Keluarga", "wajib": 1}]
JENIS = [
    # ---- daftar surat keterangan desa (kode klasifikasi dari pemilik)
    ("SKD", "Surat Keterangan Domisili", "202",
     {"sections": [orang(), isian("lainnya", "Keperluan", KEP)]},
     YBT + "{{ biodata(pemohon) }}"
     + "<p>Orang tersebut di atas benar-benar penduduk dan berdomisili di Desa {{ desa.nama }} Kecamatan "
       "{{ desa.kecamatan }} Kabupaten {{ desa.kabupaten }}, sesuai alamat tersebut di atas.</p>"
     + KEPERLUAN + DEMIKIAN, KTP_KK),
    ("SKDO", "Surat Keterangan Domisili Organisasi", "203",
     {"sections": [orang("penanggung_jawab", "Penanggung Jawab / Ketua", ["nama", "nik", "pekerjaan", "alamat"]),
                   isian("organisasi", "Data Organisasi",
                         f("nama_organisasi", "Nama organisasi/lembaga", required=True, register=True),
                         f("bidang_organisasi", "Bidang/jenis kegiatan"),
                         f("alamat_organisasi", "Alamat sekretariat", required=True),
                         f("akta_organisasi", "Nomor akta/SK pendirian"), KEP)]},
     YBT + baris(("Nama Organisasi", "{{ nama_organisasi }}"), ("Bidang Kegiatan", "{{ bidang_organisasi }}"),
                 ("Nomor Akta/SK", "{{ akta_organisasi }}"), ("Alamat Sekretariat", "{{ alamat_organisasi }}"))
     + "<p>benar berdomisili di Desa {{ desa.nama }} Kecamatan {{ desa.kecamatan }} Kabupaten {{ desa.kabupaten }}, "
       "dengan penanggung jawab:</p>{{ biodata(penanggung_jawab) }}" + KEPERLUAN + DEMIKIAN,
     [{"nama": "KTP Ketua", "wajib": 1}, {"nama": "Akta/SK Pendirian", "wajib": 0}]),
    ("SKTM", "Surat Keterangan Tidak Mampu", "204",
     {"sections": [orang(), isian("lainnya", "Keperluan", KEP)]},
     YBT + "{{ biodata(pemohon) }}" + PENDUDUK
     + "<p>Sepanjang sepengetahuan kami, orang tersebut di atas benar-benar berasal dari keluarga tidak mampu "
       "(kurang mampu) secara ekonomi.</p>" + KEPERLUAN + DEMIKIAN, KTP_KK),
    ("SKU", "Surat Keterangan Usaha", "205",
     {"sections": [orang(), isian("usaha", "Data Usaha",
                                  f("nama_usaha", "Nama usaha"),
                                  f("jenis_usaha", "Jenis usaha", required=True, register=True),
                                  f("alamat_usaha", "Alamat/lokasi usaha", required=True),
                                  f("mulai_usaha", "Berdiri sejak (tahun)"), KEP)]},
     YBT + "{{ biodata(pemohon) }}" + PENDUDUK
     + "<p>Sepanjang sepengetahuan kami, orang tersebut di atas benar-benar mempunyai usaha sebagai berikut:</p>"
     + baris(("Nama Usaha", "{{ nama_usaha }}"), ("Jenis Usaha", "{{ jenis_usaha }}"),
             ("Alamat Usaha", "{{ alamat_usaha }}"), ("Berdiri Sejak", "{{ mulai_usaha }}"))
     + KEPERLUAN + DEMIKIAN, KTP_KK),
    ("SREK", "Surat Rekomendasi", "207",
     {"sections": [orang(), isian("lainnya", "Rekomendasi",
                                  f("tujuan", "Ditujukan kepada", required=True, register=True), KEP)]},
     YBT + "{{ biodata(pemohon) }}" + PENDUDUK
     + "<p>Pada prinsipnya kami tidak keberatan dan memberikan rekomendasi kepada orang tersebut di atas untuk "
       "keperluan {{ keperluan }} kepada {{ tujuan }}.</p>"
     + "<p>Demikian surat rekomendasi ini dibuat untuk dipergunakan sebagaimana mestinya.</p>", KTP_KK),
    ("SKH", "Surat Keterangan Kehilangan", "208",
     {"sections": [orang(), isian("kehilangan", "Data Kehilangan",
                                  f("barang_hilang", "Barang/dokumen yang hilang", "textarea", required=True,
                                    register=True),
                                  f("tanggal_hilang", "Tanggal kehilangan", "date"),
                                  f("lokasi_hilang", "Lokasi kehilangan"), KEP)]},
     YBT + "{{ biodata(pemohon) }}" + PENDUDUK
     + "<p>Menurut keterangan yang bersangkutan, telah kehilangan {{ barang_hilang }} pada tanggal "
       "{{ tgl_indo(tanggal_hilang) }} di {{ lokasi_hilang }}.</p>" + KEPERLUAN + DEMIKIAN, KTP_KK),
    ("SKTTS", "Surat Keterangan Tanah Tidak Sengketa", "210",
     {"sections": [orang(), isian("tanah", "Data Tanah",
                                  f("lokasi_tanah", "Lokasi tanah", required=True, register=True),
                                  f("luas_tanah", "Luas (m²)", "number", required=True),
                                  f("bukti_tanah", "Bukti kepemilikan (SPPT/Pipil/Sertifikat) & nomor"),
                                  KEP),
                   {"key": "batas", "label": "Batas-batas Tanah", "type": "daftar",
                    "columns": [f("arah", "Arah", "select", options=["Utara", "Timur", "Selatan", "Barat"]),
                                f("berbatasan", "Berbatasan dengan")]}]},
     YBT + "{{ biodata(pemohon) }}" + PENDUDUK
     + "<p>Orang tersebut di atas benar memiliki/menguasai sebidang tanah yang terletak di {{ lokasi_tanah }} "
       "seluas {{ luas_tanah }} m² dengan bukti kepemilikan {{ bukti_tanah }}, dengan batas-batas:</p>"
     + "{{ tabel(batas) }}"
     + "<p>Sepanjang sepengetahuan kami, tanah tersebut sampai saat ini tidak dalam sengketa dengan pihak mana "
       "pun.</p>" + KEPERLUAN + DEMIKIAN,
     KTP_KK + [{"nama": "SPPT/Bukti kepemilikan tanah", "wajib": 1}]),
    ("SKPOT", "Surat Keterangan Penghasilan Orang Tua", "211",
     {"sections": [orang("orang_tua", "Data Orang Tua", ["nama", "nik", "ttl", "pekerjaan", "alamat"]),
                   orang("anak", "Data Anak", ["nama", "nik", "ttl"]),
                   isian("lainnya", "Penghasilan",
                         f("penghasilan", "Penghasilan per bulan", "rupiah", required=True), KEP)]},
     YBT + "{{ biodata(orang_tua) }}" + PENDUDUK
     + "<p>Orang tersebut di atas adalah orang tua dari:</p>{{ biodata(anak) }}"
     + "<p>dan benar mempunyai penghasilan rata-rata sebesar {{ penghasilan }} "
       "({{ terbilang(penghasilan, \"rupiah\") }}) per bulan.</p>" + KEPERLUAN + DEMIKIAN, KTP_KK),

    ("SKBM", "Surat Keterangan Belum Menikah", "148.1",
     {"sections": [orang(tampilkan=["nama", "ttl", "jenis_kelamin", "agama", "status_perkawinan", "pekerjaan",
                                    "kewarganegaraan", "alamat"]),
                   isian("lainnya", "Keperluan", f("keperluan", "Keperluan (salah satu syarat ...)", required=True,
                                                    register=True))]},
     YBT + "{{ biodata(pemohon) }}" + PENDUDUK
     + "<p>Sejauh pengamatan dan penelitian yang kami lakukan, memang benar yang bersangkutan belum pernah sama "
       "sekali melangsungkan pernikahan sampai dengan saat ini.</p>"
     + "<p>Surat keterangan ini diberikan kepada yang bersangkutan sebagai salah satu syarat {{ keperluan }}.</p>"
     + DEMIKIAN, KTP_KK),
    # ---- contoh format surat desa (PDF "surat yang sering dibuat"), klasifikasi 470 = kependudukan
    ("SKET", "Surat Keterangan", "470",
     {"sections": [orang(), {"key": "keterangan", "label": "Keterangan", "type": "teks_bebas", "required": True},
                   isian("lainnya", "Keperluan", KEP)]},
     YBT + "{{ biodata(pemohon) }}" + PENDUDUK + "{{ keterangan }}" + KEPERLUAN + DEMIKIAN, KTP_KK),
    ("SKL", "Surat Keterangan Kelahiran", "470",
     {"sections": [orang("ibu", "Data Ibu", ["nik", "nama", "ttl", "alamat"]),
                   orang("ayah", "Data Bapak", ["nik", "nama", "ttl", "alamat"]),
                   isian("anak", "Data Anak",
                         f("nama_anak", "Nama lengkap anak", required=True, register=True),
                         f("anak_ke", "Anak ke-", "number"),
                         f("jk_anak", "Jenis kelamin", "select", required=True, options=["Laki-laki", "Perempuan"]),
                         f("tempat_lahir_anak", "Tempat lahir (kabupaten)", required=True),
                         f("tanggal_lahir_anak", "Tanggal lahir", "date", required=True),
                         f("alamat_anak", "Alamat anak"),
                         f("penolong", "Penolong kelahiran", "select", options=["Bidan", "Dokter", "Dukun Bayi"]),
                         f("alamat_penolong", "Alamat penolong"))]},
     YBT + baris(("Nama Lengkap Anak", "<b>{{ nama_anak }}</b>"), ("Anak Ke", "{{ anak_ke }}"),
                 ("Jenis Kelamin", "{{ jk_anak }}"),
                 ("Dilahirkan di", "{{ tempat_lahir_anak }}, {{ tgl_indo(tanggal_lahir_anak) }}"),
                 ("Alamat Anak", "{{ alamat_anak }}"), ("Penolong Kelahiran", "{{ penolong }}"),
                 ("Alamat Penolong", "{{ alamat_penolong }}"))
     + '<p style="text-indent: 0">Adalah anak kandung dari suami istri tersebut di bawah ini:</p>'
     + '<p style="text-indent: 0"><b>IBU</b></p>{{ biodata(ibu) }}'
     + '<p style="text-indent: 0"><b>BAPAK</b></p>{{ biodata(ayah) }}'
     + "<p>Surat keterangan ini dipergunakan untuk: Persyaratan pembuatan akta kelahiran.</p>" + DEMIKIAN,
     [{"nama": "KTP Orang Tua", "wajib": 1}, {"nama": "Kartu Keluarga", "wajib": 1},
      {"nama": "Surat Keterangan Lahir dari Bidan/RS", "wajib": 0}]),
    ("SKK", "Surat Keterangan Kematian", "470",
     {"sections": [orang("almarhum", "Data yang Meninggal",
                         ["nama", "nik", "no_kk", "ttl", "jenis_kelamin", "kewarganegaraan", "agama",
                          "status_perkawinan", "pekerjaan", "alamat"]),
                   isian("kematian", "Data Kematian",
                         f("hari_meninggal", "Hari", "select", options=HARI),
                         f("tanggal_meninggal", "Tanggal meninggal", "date", required=True, register=True),
                         f("tempat_kematian", "Tempat kematian", required=True),
                         f("sebab_kematian", "Sebab kematian"), KEP)]},
     YBT + "{{ biodata(almarhum) }}" + '<p style="text-indent: 0">Telah meninggal dunia pada:</p>'
     + baris(("Hari / Tanggal", "{{ hari_meninggal }}, {{ tgl_indo(tanggal_meninggal) }}"),
             ("Tempat Kematian", "{{ tempat_kematian }}"), ("Sebab Kematian", "{{ sebab_kematian }}"))
     + KEPERLUAN + DEMIKIAN,
     [{"nama": "KTP Almarhum", "wajib": 0}, {"nama": "Kartu Keluarga", "wajib": 1}]),
    ("SKBN", "Surat Keterangan Beda Nama", "470",
     {"sections": [orang(tampilkan=["nama", "nik", "ttl", "alamat"]),
                   {"key": "dokumen", "label": "Nama pada Dokumen", "type": "daftar",
                    "columns": [f("dokumen", "Dokumen", required=True), f("nomor", "Nomor"),
                                f("nama", "Nama tertulis", required=True)]},
                   isian("lainnya", "Keterangan",
                         f("dokumen_acuan", "Nama yang benar sesuai (KTP/KK/Ijazah/Akta)", required=True), KEP)]},
     YBT + "{{ biodata(pemohon) }}"
     + "<p>Berdasarkan dokumen-dokumen berikut:</p>{{ tabel(dokumen) }}"
     + "<p>Nama-nama tersebut di atas adalah milik satu orang, yaitu nama yang tercantum dalam "
       "{{ dokumen_acuan }}.</p>" + KEPERLUAN + DEMIKIAN,
     KTP_KK + [{"nama": "Dokumen yang berbeda nama", "wajib": 1}]),
    ("SKAW", "Surat Keterangan Ahli Waris", "470",
     {"sections": [orang("pewaris", "Data Pewaris (yang meninggal)", ["nama", "nik", "alamat"]),
                   isian("kematian", "Kematian Pewaris",
                         f("tanggal_meninggal", "Tanggal meninggal", "date", required=True),
                         f("tempat_meninggal", "Meninggal di (desa/kecamatan/kabupaten)"), KEP),
                   {"key": "ahli_waris", "label": "Daftar Ahli Waris", "type": "daftar",
                    "columns": [f("nama", "Nama", required=True), f("ttl", "Tempat/Tgl. Lahir"), f("nik", "NIK"),
                                f("pekerjaan", "Pekerjaan"), f("alamat", "Alamat"), f("hubungan", "Hubungan")]}]},
     YBT + "{{ tabel(ahli_waris) }}"
     + "<p>Berdasarkan sepengetahuan kami, orang-orang tersebut di atas adalah benar ahli waris dari almarhum/almarhumah "
       "<b>{{ pewaris.nama }}</b> yang telah meninggal pada tanggal {{ tgl_indo(tanggal_meninggal) }} di "
       "{{ tempat_meninggal }}.</p>" + KEPERLUAN + DEMIKIAN,
     [{"nama": "KTP Ahli Waris", "wajib": 1}, {"nama": "Kartu Keluarga", "wajib": 1},
      {"nama": "Surat Keterangan Kematian", "wajib": 1}]),
    ("SB", "Surat Biasa", "000",
     {"layout": "dinas", "sections": [KEPALA_DINAS,
                                      {"key": "isi", "label": "Isi Surat", "type": "teks_bebas", "required": True}]},
     "{{ isi }}" + DEMIKIAN_SB, []),
    ("SU", "Surat Undangan", "005",
     {"layout": "dinas", "sections": [KEPALA_DINAS,
                                      isian("detail_acara", "Acara",
                                            f("hari", "Hari", "select", required=True, options=HARI),
                                            f("tanggal_acara", "Tanggal", "date", required=True),
                                            f("pukul", "Pukul", required=True),
                                            f("tempat_acara", "Tempat", required=True),
                                            f("acara", "Acara", "textarea", required=True, register=True))]},
     "<p>Dengan hormat,</p><p>Mengharap kehadiran Bapak/Ibu/Saudara pada:</p>"
     + baris(("Hari", "{{ hari }}"), ("Tanggal", "{{ tgl_indo(tanggal_acara) }}"), ("Pukul", "{{ pukul }}"),
             ("Tempat", "{{ tempat_acara }}"), ("Acara", "{{ acara }}"))
     + "<p>Mengingat pentingnya acara tersebut, dimohon hadir tepat waktu. Atas perhatian dan kehadirannya "
       "diucapkan terima kasih.</p>", []),
]


def q(v):
    return "'" + str(v).replace("'", "''") + "'"


def main():
    codes, rows = set(), []
    for i, (code, name, klas, skema, redaksi, syarat) in enumerate(JENIS, start=10):
        assert code not in codes, code
        codes.add(code)
        skema = service.validate_skema(skema)
        redaksi = service.clean_template(redaksi, skema)
        rows.append(f"({q(code)}, {q(name)}, {q(klas)}, {q(json.dumps(skema, ensure_ascii=False))}::jsonb, "
                    f"{q(redaksi)}, {q(json.dumps(syarat, ensure_ascii=False))}::jsonb, 1, {i}, now())")
    sql = f"""-- =====================================================================
-- 011: seed jenis surat yang sering dibuat (format contoh surat desa) + daftar surat keterangan desa.
--   DIBUAT OTOMATIS oleh scripts/seed_jenis_surat.py (skema & redaksi divalidasi service). Jangan edit manual.
--   Layout "dinas" (Surat Biasa, Undangan) disimpan di skema_form.layout.
-- Aman dijalankan ulang (ON CONFLICT DO NOTHING). Transaksi dibungkus deploy.sh (--single-transaction).
-- =====================================================================

INSERT INTO jenis_surat (code, name, kode_klasifikasi, skema_form, template_isi, persyaratan, versi, sort_order, created_at)
VALUES
{(","+chr(10)).join(rows)}
ON CONFLICT (code) DO NOTHING;

"""
    OUT.write_text(sql)
    print(f"{OUT.name}: {len(rows)} jenis surat")


if __name__ == "__main__":
    main()
