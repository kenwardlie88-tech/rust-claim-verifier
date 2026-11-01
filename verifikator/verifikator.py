#!/usr/bin/env python3
"""Bot verifikasi temuan audit Rust/Solana — fail-closed.

Aturan yang tidak bisa dilanggar:
  1. Setiap harapan WAJIB punya nilai teramati (keluaran cargo test yang nyata).
  2. Minimal satu harapan "lulus" (serangan berhasil di versi rentan) DAN
     satu harapan "gagal" (serangan ditolak di versi diperbaiki). Tanpa dua sisi,
     putusan tidak boleh disimpan — lulus tanpa kontrol negatif bukan bukti.
  3. Daftar "tidak_diklaim" wajib ada dan tidak boleh kosong.
  4. Putusan hanya CONFIRMED bila SEMUA harapan terpenuhi. Selain itu REFUTED.

Pakai:
    python3 verifikator.py spesifikasi.json
Keluar: 0 = CONFIRMED · 1 = REFUTED · 2 = DITOLAK (berkas tidak lengkap/alat gagal)
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
KELUARAN = BASE / "evidence" / "verdicts"


def jalankan_tes(proyek: str, nama_tes: str) -> dict:
    """Jalankan satu tes di satu proyek, kembalikan hasil yang teramati."""
    direktori = BASE / proyek
    if not (direktori / "Cargo.toml").exists():
        return {"ok": None, "sebab": f"proyek tidak ditemukan: {direktori}"}

    perintah = (
        f"source {BASE}/env.sh >/dev/null 2>&1 && cd {direktori} && "
        f"cargo test --release --test poc -- --exact {nama_tes} --nocapture"
    )
    hasil = subprocess.run(
        ["bash", "-lc", perintah], capture_output=True, text=True, timeout=1800
    )
    keluaran = hasil.stdout + hasil.stderr

    pola_ok = re.compile(rf"test {re.escape(nama_tes)} \.\.\. ok")
    pola_gagal = re.compile(rf"test {re.escape(nama_tes)} \.\.\. FAILED")
    if pola_ok.search(keluaran):
        lulus = True
    elif pola_gagal.search(keluaran) or hasil.returncode != 0:
        lulus = False
    else:
        return {"ok": None, "sebab": "tes tidak menghasilkan status yang bisa dibaca"}

    return {
        "ok": lulus,
        "proyek": proyek,
        "tes": nama_tes,
        "exit": hasil.returncode,
        "baris_bukti": [
            b.strip()
            for b in keluaran.splitlines()
            if nama_tes in b and ("ok" in b or "FAILED" in b or "panicked" in b)
        ][:3],
    }


def tolak(alasan: str) -> int:
    print(f"  DITOLAK: {alasan}")
    return 2


def main() -> int:
    if len(sys.argv) < 2:
        return tolak("sebutkan berkas spesifikasi JSON")

    spesifikasi = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    id_temuan = spesifikasi.get("id", "").strip()
    klaim = spesifikasi.get("klaim", "").strip()
    harapan = spesifikasi.get("harapan", [])
    tidak_diklaim = [t for t in spesifikasi.get("tidak_diklaim", []) if t.strip()]

    if not id_temuan:
        return tolak("id temuan kosong")
    if not klaim:
        return tolak("klaim kosong — tanpa klaim tidak ada yang diverifikasi")
    if not tidak_diklaim:
        return tolak("daftar 'tidak_diklaim' kosong — batas bukti wajib dinyatakan")
    if not harapan:
        return tolak("tidak ada harapan yang diuji")

    harus_lulus = [h for h in harapan if h.get("harus") == "lulus"]
    harus_gagal = [h for h in harapan if h.get("harus") == "gagal"]
    if not harus_lulus or not harus_gagal:
        return tolak(
            "kontrol dua sisi tidak lengkap: butuh minimal satu 'lulus' (rentan) "
            "dan satu 'gagal' (diperbaiki). Lulus tanpa kontrol negatif bukan bukti."
        )

    diamati = []
    for h in harapan:
        print(f"  jalankan: {h['proyek']} :: {h['tes']} (harus {h['harus']})")
        hasil = jalankan_tes(h["proyek"], h["tes"])
        if hasil.get("ok") is None:
            return tolak(f"tidak terukur — {hasil.get('sebab')}")
        hasil["harus"] = h["harus"]
        hasil["terpenuhi"] = (hasil["ok"] is True and h["harus"] == "lulus") or (
            hasil["ok"] is False and h["harus"] == "gagal"
        )
        diamati.append(hasil)
        tanda = "OK" if hasil["terpenuhi"] else "TIDAK TERPENUHI"
        print(f"    lulus={hasil['ok']} · {tanda}")

    putusan = "CONFIRMED" if all(d["terpenuhi"] for d in diamati) else "REFUTED"

    KELUARAN.mkdir(parents=True, exist_ok=True)
    catatan = {
        "id": id_temuan,
        "klaim": klaim,
        "putusan": putusan,
        "waktu": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "harapan": diamati,
        "tidak_diklaim": tidak_diklaim,
        "lingkungan": {
            "skrip": str(Path(__file__).resolve()),
            "basis": str(BASE),
            "python": sys.version.split()[0],
        },
    }
    (KELUARAN / f"{id_temuan}.json").write_text(
        json.dumps(catatan, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    baris = [
        f"# Putusan verifikasi {id_temuan}",
        "",
        f"**Klaim:** {klaim}",
        f"**Putusan:** **{putusan}**",
        f"**Waktu:** {catatan['waktu']}",
        "",
        "## Harapan vs teramati",
        "",
        "| Proyek | Tes | Harus | Teramati | Terpenuhi |",
        "|---|---|---|---|---|",
    ]
    for d in diamati:
        baris.append(
            f"| {d['proyek']} | `{d['tes']}` | {d['harus']} | "
            f"{'lulus' if d['ok'] else 'gagal'} | {'ya' if d['terpenuhi'] else 'TIDAK'} |"
        )
    baris += ["", "## Tidak diklaim", ""] + [f"- {t}" for t in tidak_diklaim]
    (KELUARAN / f"{id_temuan}.md").write_text("\n".join(baris) + "\n", encoding="utf-8")

    print(f"  putusan: {putusan}")
    print(f"  tersimpan: {KELUARAN / (id_temuan + '.json')}")
    return 0 if putusan == "CONFIRMED" else 1


if __name__ == "__main__":
    sys.exit(main())
