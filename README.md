# Barkod Bas

Nelko P21 Bluetooth etiket yazıcısına barkod basar. Telefon uygulamasından bağımsızdır.

İki kaynak vardır:

- **Excel sütunu.** Dosya seçilir, sütun seçilir. İlk satır başlıksa atlanır. Boş olmayan her hücre kendi etiketi olur.
- **Liste.** Her satır bir etikettir. Aynı yazı beş kez yazılırsa beş etiket basılır.

**Hepsini bas** sırayı başlatır. **Durdur** kalanları keser.

Etiketler tek tek basılır. Biri yazıcıdan çıkmadan diğeri başlamaz. Hepsi birden gönderilirse yazıcı baskıyı yarıda keser. Etikete sığmayan uzun satır atlanır.

## Etiket

Barkod Code 128'dir. Rakamlarda Code C, diğer yazılarda Code B kullanılır. Barkodun yanında yazının kendisi de vardır.

Ölçü yazıcıdaki rulodan okunur. Okunamazsa 14×40 mm, 5 mm boşluk kullanılır. Yoğunluk 15'tir.

Yazıcı Bluetooth SPP (COM) üzerinden konuşur. Windows Ayarlar'da "bağlandı" deyip hemen düşmesi normaldir. Port yalnızca baskı sırasında açık kalır. Sıfır MAC adresli gelen kutu portu kullanılmaz.

## Çalıştırma

`Barkod.bat` pencereyi açar. Python paketleri (`openpyxl`, `pyserial`, `Pillow`) yoksa kurar.

Excel sayısı tam sayıysa metin olarak basılır. IMEI bilimsel gösterime dönmez.
