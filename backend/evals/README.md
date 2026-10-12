# Evaluasi kualitas Gemma

Evaluasi kualitas paragraf yang ditulis Gemma (lewat Ollama) dijalankan manual di Vast.ai, terpisah dari unit test.

- `uv run pytest` tidak pernah memanggil model sungguhan; tes memakai `FakeLlmClient` dan runner Ollama palsu.
- Evaluasi dengan model sungguhan butuh GPU, jadi dijalankan di instance Vast.ai dengan `BKDG_USE_LLM=true` dan `BKDG_OLLAMA_HOST` yang menunjuk ke Ollama di instance itu.
- Folder ini belum berisi skrip evaluasi.
