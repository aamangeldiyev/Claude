STAMPS — Reference images for stamp detection
=============================================

Place your reference stamp images in this folder.
Supported formats: .jpg, .jpeg, .png, .bmp, .tiff

Naming convention (example):
  stamp_dsp.jpg          — "Для служебного пользования"
  stamp_secret.jpg       — "Секретно"
  stamp_top_secret.jpg   — "Совершенно секретно"

Requirements for best detection:
  - Scan/crop at the highest quality you have (300 DPI or better)
  - White or near-white background
  - The stamp should fill most of the image frame (crop tightly)
  - Grayscale or colour — both work

Each image in this folder becomes one "template".
Multiple templates are all applied to every scanned file.

To generate a synthetic test stamp (Latin placeholder):
  python create_test_stamp.py
