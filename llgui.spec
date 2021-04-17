# -*- mode: python ; coding: utf-8 -*-
# use command pyinstaller --clean --onefile --additional-hooks-dir=. --log-level DEBUG --distpath "C:/Users/Hutto/loggerloader/" C:/Users/Hutto/loggerloader/setup.spec

block_cipher = None


a = Analysis(['C:\\Users\\Hutto\\loggerloader\\llgui.py'],
             pathex=['C:\\Users\\Hutto\\loggerloader'],
             binaries=[],
             hiddenimports = ["babel.dates", "babel.numbers"],
             datas=[('C:\\Users\\Hutto\\loggerloader\\data_files\\', 'data_files'),
             ('C:\\ProgramData\\Anaconda3\\envs\\pyll37\\Lib\\site-packages\\matplotlib\\mpl-data\\', "matplotlib/mpl-data"),],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
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
          console=True )
