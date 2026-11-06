# Barkod Bas

Prints barcodes on a Nelko P21 Bluetooth label printer. It does not depend on the phone app.

Two sources:

- **Excel column.** Pick a file and a column. The first row can be skipped as a header. Every non-empty cell becomes its own label.
- **List.** Each line is one label. The same text on five lines prints five labels.

**Hepsini bas** starts the queue. **Durdur** stops whatever is left.

Labels print one at a time. The next job is not sent until the current label has come out. Sending them all at once makes the printer cut the print in half. A line that is too long for the label is skipped.

## Label

The barcode is Code 128. Digits use Code C. Other text uses Code B. The text itself is printed beside the bars.

Size is read from the roll in the printer. If that fails, the job uses 14×40 mm with a 5 mm gap. Density is 15.

The printer speaks Bluetooth SPP over a COM port. Windows Settings showing Connected and then immediately Disconnected is normal. The port stays open only while labels are printing. The incoming port with an all-zero MAC address is ignored.

## How to run

`Barkod.bat` opens the window. If `openpyxl`, `pyserial`, or `Pillow` is missing, the batch file installs them.

A whole number read from Excel is printed as that number, so an IMEI is not turned into scientific notation.
