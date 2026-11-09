
# Sortir File Kuliah

Aplikasi kecil untuk Windows yang memantau folder **Downloads**. Setiap ada file materi baru, muncul popup untuk memilih mata kuliah tujuan, lalu file langsung dipindahkan ke folder mata kuliah yang dipilih.

## Fitur

- Popup pilih mata kuliah muncul otomatis saat ada file baru di Downloads.
- Download banyak file sekaligus digabung dalam **satu popup** dengan kotak centang. Satu klik memindahkan semua file yang dicentang.
- File yang bukan materi (installer, video, dan sejenisnya) diabaikan, tidak ada popup.
- Pilihan **Bukan materi kuliah** membiarkan file tetap di Downloads.
- Pilihan **Jangan tanya lagi** untuk tipe file tertentu.
- Berjalan di background dengan ikon di system tray.
- Bisa menyala otomatis saat Windows dinyalakan.
- Pengaturan lewat tampilan, tidak perlu mengedit kode.
- File bernama sama tidak menimpa file lama (diberi akhiran `_1`, `_2`, dan seterusnya).

## Isi folder

| File                 | Fungsi                                     |
| -------------------- | ------------------------------------------ |
| `sortir_kuliah.py` | Kode aplikasi                              |
| `build.bat`        | Membuat `SortirFileKuliah.exe` dari kode |
| `README.md`        | Panduan ini                                |

## 1. Membuat file .exe (sekali saja)

Syarat: Windows, Python sudah terpasang (perintah `py` bisa dipakai), dan laptop terhubung internet.

1. Taruh `sortir_kuliah.py` dan `build.bat` dalam satu folder.
2. Klik dua kali `build.bat`. Script akan memasang library yang dibutuhkan (`watchdog`, `pystray`, `pillow`, `pyinstaller`) lalu membuat file `.exe`.
3. Setelah muncul tulisan "Selesai", ambil hasilnya di folder `dist`: `dist\SortirFileKuliah.exe`.
4. Pindahkan `SortirFileKuliah.exe` ke lokasi **permanen**, misalnya `C:\SortirKuliah\`. Jangan dijalankan dari Downloads atau folder sementara, karena fitur auto-start mencatat lokasi file ini.

> Jika build gagal, catat pesan error-nya. Versi Python yang sangat baru kadang belum didukung penuh oleh salah satu library.

## 2. Pertama kali dijalankan

1. Klik dua kali `SortirFileKuliah.exe`.
2. Jendela **Pengaturan** terbuka otomatis. Isi:
   - **Folder induk**: klik *Pilih...*, arahkan ke folder tempat folder mata kuliah berada.
   - **Daftar mata kuliah**: tambah atau hapus sesuai kebutuhan. Nama harus sama dengan nama folder.
   - **Tipe file** yang memunculkan popup (bawaan: PDF, Word, PowerPoint, Excel, TXT, ZIP, RAR, JPG, PNG).
   - Centang **Jalankan otomatis saat Windows menyala** bila diinginkan.
3. Klik **Simpan**. Ikon muncul di system tray (pojok kanan bawah, bisa tersembunyi di balik panah ^).

Daftar mata kuliah bawaan: BINDO, DASKOM A, DASKOM B, FIDAS, GAMTEK, KIMDAS, MATDAS A, MATDAS B, PEGANTAR TEKDUS.

## 3. Cara memakai

1. Download file dari WhatsApp (atau mana saja) ke folder **Downloads**.
2. Setelah file selesai terunduh, popup muncul di pojok kanan bawah.
3. Centang file yang mau dipindahkan, lalu klik nama mata kuliahnya.
4. Pilihan lain di popup:
   - **Pilih semua** / **Kosongkan**: mengatur centang sekaligus.
   - **Bukan materi kuliah**: file yang dicentang dibiarkan di Downloads.
   - **Jangan tanya lagi untuk tipe file yang dicentang**: tipe itu tidak memicu popup lagi (bisa diaktifkan kembali di Pengaturan).
5. Jika popup tidak disentuh, popup menutup sendiri setelah 60 detik tanpa aktivitas. File tetap aman di Downloads.

Menu klik kanan pada ikon tray: **Jeda pemantauan**, **Buka folder Downloads**, **Pengaturan**, **Keluar**.

## 4. Membagikan ke teman

1. Kirim **hanya** `SortirFileKuliah.exe`. Teman tidak perlu memasang Python.
2. Jika Windows SmartScreen menampilkan peringatan "Unknown publisher", pilih **More info**, lalu **Run anyway**. Peringatan ini muncul untuk semua aplikasi tanpa sertifikat berbayar.
3. Setiap teman mengisi Pengaturan sendiri saat pertama menjalankan, karena lokasi folder kuliah tiap orang berbeda.

## 5. Mengubah kode / memperbarui aplikasi

1. Klik kanan ikon tray, pilih **Keluar** (supaya `.exe` tidak terkunci).
2. Edit `sortir_kuliah.py`, lalu jalankan `build.bat` lagi.
3. Ganti `.exe` lama dengan yang baru dari folder `dist`.
4. Jika `.exe` dipindah ke lokasi lain, buka Pengaturan lalu klik **Simpan** sekali lagi agar auto-start mencatat lokasi baru.

## Lokasi data

| Data       | Lokasi                                                           |
| ---------- | ---------------------------------------------------------------- |
| Pengaturan | `%APPDATA%\SortirFileKuliah\config.json`                       |
| Auto-start | Registry: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |

Untuk mengembalikan ke pengaturan awal, tutup aplikasi lalu hapus file `config.json`.

## Pemecahan masalah

| Masalah                                             | Penyebab dan solusi                                                                                                                                             |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Popup tidak muncul                                  | Cek apakah pemantauan sedang dijeda (menu tray). Cek juga apakah tipe filenya ada di daftar *Tipe file* di Pengaturan.                                        |
| Popup tidak muncul untuk file dari WhatsApp Desktop | WhatsApp mungkin menyimpan ke folder lain, bukan Downloads. Ubah lokasi simpan di pengaturan WhatsApp atau browser.                                             |
| File masuk ke folder baru, bukan folder lama        | Folder induk di Pengaturan belum sesuai. Buka Pengaturan dan pilih ulang folder induknya.                                                                       |
| Muncul pesan "Aplikasi sudah berjalan"              | Aplikasi sudah aktif. Cek ikon di system tray.                                                                                                                  |
| Auto-start tidak jalan setelah `.exe` dipindah    | Buka Pengaturan, klik **Simpan** sekali lagi.                                                                                                             |
| Pesan "Sebagian file gagal dipindahkan"             | File sedang dibuka aplikasi lain, atau folder tujuan tidak bisa ditulis. Tutup aplikasi yang membukanya lalu coba lagi. File yang gagal tetap ada di Downloads. |

## Catatan

- Aplikasi hanya memantau satu level di folder Downloads (tidak masuk ke subfolder).
- Aplikasi tidak menghapus file apa pun. File hanya dipindahkan atas pilihan pengguna.
- Aplikasi tidak terhubung ke akun WhatsApp dan tidak mengirim data ke internet.
