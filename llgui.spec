# -*- mode: python ; coding: utf-8 -*-
# packages files are much smaller with a pure pip installation
# use command pyinstaller --clean C:/Users/paulinkenbrandt/loggerloader/llgui.spec

block_cipher = None

a = Analysis(['C:\\Users\\paulinkenbrandt\\loggerloader\\loggerloader\\llgui.py'],
             pathex=['C:\\Users\\paulinkenbrandt\\loggerloader\\loggerloader'],
             binaries=None,
             hiddenimports = ["babel.dates", "babel.numbers"],
             datas=[('C:\\Users\\paulinkenbrandt\\loggerloader\\data_files\\', 'data_files'),
             ('C:\\Users\\paulinkenbrandt\\loggerloader\\themes\\', 'themes'),
             ('C:\\Users\\paulinkenbrandt\\loggerloader\\venv\\Lib\\site-packages\\matplotlib\\mpl-data\\', "matplotlib/mpl-data")],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

splash = Splash('./data_files/SplashPic.png',
                binaries=a.binaries,
                datas=a.datas,
                text_pos=(10, 50),
                text_size=12,
                text_color='black')

exe = EXE(pyz,
          a.scripts,
          splash,
          splash.binaries,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='loggerloader',
          debug=True,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False )
