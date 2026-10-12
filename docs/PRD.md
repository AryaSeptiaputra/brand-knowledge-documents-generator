# PRD — Brand Knowledge Document Generator

**Versi:** 0.8 · **Tanggal:** 2026-10-12 · **Pemilik:** Arya · **Status:** Draf

## 1. Ringkasan
Website yang mengubah **fakta dan data brand** yang ditulis pengguna dalam format YAML bebas menjadi dokumen PDF **Kebijakan**, **Panduan**, dan **Product Knowledge** versi pelanggan — mudah dibaca orang non-teknis sekaligus mudah diproses AI atau sistem RAG.

## 2. Masalah
Data brand jarang tersedia dalam bentuk yang siap dipakai AI: tercecer, tidak terstruktur, dan tanpa metadata, sehingga AI atau RAG sulit menemukan informasi yang tepat dan mudah salah menjawab.

## 3. Tujuan / Non-tujuan
| Tujuan | Non-tujuan (MVP) |
|---|---|
| Dokumen PDF yang terbaca manusia **dan** siap dipakai AI/RAG, dari data YAML bebas | Membangun chatbot atau RAG-nya sendiri |
| Isi 100% dari data: tidak ada yang dikarang, tidak ada yang hilang | Mengambil data dari website atau PDF |
| Portofolio solo dev | Akun pengguna, multi-bahasa, versi internal/CS |

## 4. Pengguna
- **Penulis data:** pemilik atau admin brand
- **Pembaca dokumen:** pelanggan (non-teknis)
- **Pemakai dokumen:** sistem AI/RAG atau chatbot brand

## 5. Jenis data
| Jenis data | Isi | Contoh |
|---|---|---|
| **Pengetahuan umum brand** | Informasi yang berlaku untuk seluruh brand | Retur, pengiriman, pembayaran, garansi |
| **Pengetahuan produk** | Informasi milik satu produk tertentu | Ukuran, bahan, varian per produk |

Contoh data (bahan masukan, bukan format yang dikunci):

```yaml
brand: Kaos Rimba
retur:
  batas_hari: 7
  syarat: [label masih terpasang, belum dicuci, ada bukti pembelian]
  ongkir_retur: ditanggung pembeli kecuali salah kirim/cacat
pengiriman:
  kurir: [JNE, J&T, SiCepat]
  estimasi: {jawa: "2-3 hari", luar_jawa: "4-7 hari"}
  gratis_ongkir_min: 300000
product:
  kaos boxy:
    size:
      S: {lebar_dada_cm: 50, panjang_cm: 68}
      M: {lebar_dada_cm: 52, panjang_cm: 70}
    bahan: cotton combed 24s
```

## 6. Fitur inti
| # | Fitur |
|---|---|
| F1 | Tulis data YAML bebas langsung di website (hanya nama brand wajib; tanpa unggah file data) + contoh siap pakai |
| F2 | Pemeriksaan format dengan pesan jelas dan letak kesalahannya |
| F3 | Pengelompokan data ke 3 jenis dokumen; satu data boleh masuk lebih dari satu jenis; pengguna bisa mengubahnya |
| F4 | Penyusunan dokumen versi pelanggan dari data, dengan rujukan sumber per bagian (hanya di pratinjau) |
| F5 | Pengecekan: tidak ada isi karangan, cakupan data 100% |
| F6 | Saran kelengkapan data (tidak masuk dokumen) |
| F7 | Pratinjau dan unduh PDF |
| F8 | PDF ramah RAG: teks asli (bukan gambar), struktur judul jelas, satu topik per bagian, tabel sebagai tabel teks, metadata dokumen (brand, jenis, tanggal) |
| F9 | Unggah logo brand di halaman pratinjau & unduh (opsional; PNG/JPG/SVG; bisa diganti/dihapus) — satu-satunya file yang boleh diunggah; tampil di header pratinjau dan setiap PDF tanpa perlu generate ulang |

## 7. Kriteria berhasil
*Belum ditentukan.*

## 8. Keputusan
| Topik | Keputusan |
|---|---|
| Input | Fakta/data brand, format YAML bebas |
| Jenis data | Pengetahuan umum brand dan pengetahuan produk |
| Output | PDF — mempertahankan keterbacaan untuk orang non-teknis |
| Versi | Pelanggan saja |
| Pengelompokan | Satu data boleh masuk lebih dari satu jenis dokumen |
| Logo | Opsional, diunggah sebagai file gambar di halaman pratinjau & unduh (setelah dokumen dibuat); pengecualian satu-satunya dari aturan "tanpa unggah file" |

## 9. Keputusan perancangan modul
| Topik | Keputusan |
|---|---|
| Jenis data | Semua yang ada di bawah kunci `product` (juga `produk`/`products`) = pengetahuan produk; anak langsungnya = nama produk. Selain itu = pengetahuan umum brand |
| Pemetaan awal ke dokumen | Aturan deterministik + kamus kata kunci kecil: produk → Product Knowledge; umum → Kebijakan; section yang namanya cocok kamus panduan (cara, langkah, panduan, perawatan, ukuran/size, …) juga → Panduan; atribut ukuran produk juga → Panduan. Pengguna bisa mengubahnya |
| Bentuk isi dokumen | Template + LLM terbatas: struktur (judul, bagian, tabel, daftar) dari template mengikuti urutan YAML; LLM hanya menulis paragraf penjelas pendek berbahasa Indonesia formal-ramah dengan sapaan "Anda", tanpa langkah yang tidak ada di data; fallback berupa kalimat template per fakta |
| Pemeriksaan isi | Deterministik berlapis: paragraf ditolak bila rujukan sumbernya tidak sah, memuat angka, atau memuat nama/istilah khusus yang tidak ada di fakta sumbernya; fakta yang belum tercakup ditambahkan sebagai kalimat template |

Rincian teknis: `docs/technical-design.md` §9.

### Masih ditangguhkan
- Penanganan potongan berisi sama di beberapa dokumen saat dipakai RAG

## 10. Keputusan teknis

### Lingkungan
| Topik | Keputusan |
|---|---|
| Uji coba | Instance sewa Vast.ai, GPU RTX 3090 24 GB, diakses lewat SSH (website dibuka lewat SSH port forwarding). Hanya untuk menguji hasil generate dokumen |
| Pengembangan lokal | Laptop: frontend (Vite dev server) + backend di WSL2; bagian non-AI dikembangkan tanpa GPU dengan mode tanpa model |
| Hosting | Dipertimbangkan lagi setelah hasil generate baik |

### Backend (Python, dikelola dengan uv)
| Kebutuhan | Pustaka |
|---|---|
| API web | FastAPI + Uvicorn |
| Model data & konfigurasi | Pydantic v2 + pydantic-settings |
| Validasi & ekstraksi fakta YAML | ruamel.yaml (posisi baris/kolom untuk pesan error dan rujukan sumber) |
| Template dokumen | Jinja2 — satu template untuk pratinjau dan PDF |
| PDF | WeasyPrint |
| Pengujian | pytest + httpx |
| Kualitas kode | ruff + mypy/pyright |

### Frontend (React + Vite + TypeScript)
| Kebutuhan | Pustaka |
|---|---|
| Editor YAML | CodeMirror 6 + lang-yaml |
| Komunikasi API | TanStack Query |
| Tipe API | openapi-typescript + openapi-fetch (dari skema OpenAPI FastAPI) |
| UI | Tailwind CSS + shadcn/ui |
| Pratinjau dokumen | HTML yang dirender backend (template yang sama dengan PDF), ditampilkan di iframe |
| Pengujian | Vitest + Testing Library |
| Lint & format | Biome |
| Package manager | pnpm |

Saat hosting nanti, hasil build React (`dist/`) disajikan oleh backend dalam satu port.

### Model AI
| Topik | Keputusan |
|---|---|
| Model runner | Ollama ≥ 0.31.2 |
| Client | Library `ollama` (Python), dibungkus adapter di Document Composer agar runner bisa diganti |
| Model | Satu model: Gemma 4 26B A4B QAT (`gemma4:26b-a4b-it-qat`, ±16 GB, Apache 2.0) |
| Structured output | Parameter `format` dengan JSON Schema dari Pydantic; hasil divalidasi Pydantic dan diulang bila tidak sah |
| Parameter awal | Konteks ±8K token; temperature 0 — diuji saat uji coba di Vast.ai |

## 11. Dibahas nanti
Hosting, penyimpanan data (bila dibutuhkan setelah MVP), dan kriteria berhasil (bagian 7).
