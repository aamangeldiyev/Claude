STAMPS — Reference images for stamp detection
=============================================

Place your stamp images here before running augment_stamps.py.
Supported formats: .jpg, .jpeg, .png, .bmp

Requirements for best results:
  - Crop tightly around the stamp (minimal empty border)
  - White or near-white background
  - 300 DPI or better if scanned; phone photo is fine too
  - Grayscale or colour — both work

One image per stamp type. Example:
  stamp_dsp.png          — "Для служебного пользования"
  stamp_secret.png       — "Секретно"

After adding new stamps, retrain:
  python train/augment_stamps.py
  python train/train_model.py
  build_windows.bat
