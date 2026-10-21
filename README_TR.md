# Network Diagnostic Tool — Türkçe Rehber

**Amaç:** Windows, macOS ve Linux üzerinde temel ağ bağlantı sorunlarını incelemek, DNS/ping/TCP/HTTPS denemelerini kullanıcı talebiyle yapmak ve HTML/JSON raporları hazırlamak.

> Bu bir portföy ve öğrenim projesidir. Gerçek cihaz bilgilerinin bulunduğu raporları paylaşmadan önce özel IP adreslerini ve bilgisayar adlarını kontrol edin. Ağ ayarlarını değiştirmez.

## Gereksinimler

- Python 3.10 veya üzeri
- İlk çalıştırma için ek Python paketi gerekmiyor
- Uygulama kendi bilgisayarınızda `127.0.0.1` üzerinde çalışır

## macOS

```bash
bash Start-Network-Diagnostic-Tool.command
```

## Windows

`Start-Network-Diagnostic-Tool.bat` dosyasını çalıştırın; alternatif olarak Python yüklü Komut İstemi'nde `py -3 -m netdiag.dashboard` komutunu kullanın.

## Linux

```bash
bash start-linux.sh
```

## Demo ve testler

Gerçek ağ sorgulaması yapmadan örnek veri ekranı:

```bash
python3 -m netdiag.dashboard --demo
```

Komut satırı ile örnek rapor:

```bash
python3 -m netdiag --demo --output-dir reports
```

Birim testleri:

```bash
python3 -m unittest discover -s tests -v
```

**Kapsam:** DNS, ping, TCP bağlantısı, HTTPS erişimi, ağ arayüz bilgileri ve yerel HTML/JSON raporları. Sistem izinleri ve ağ güvenlik duvarı bazı testlerin sonucunu etkileyebilir.

**English / Deutsch:** [README.md](README.md) · [Portföy vaka çalışması](docs/PORTFOLIO_CASE_STUDY.md)
