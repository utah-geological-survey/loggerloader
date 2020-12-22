# -*- mode: python ; coding: utf-8 -*-
# use command pyinstaller --clean --onefile --log-level DEBUG --distpath "C:/Users/Hutto/PycharmProjects/loggerloader/" C:/Users/Hutto/PycharmProjects/loggerloader/llgui.spec

block_cipher = None


a = Analysis(['C:\\Users\\Hutto\\PycharmProjects\\loggerloader\\loggerloader\\llgui.py'],
             pathex=['C:\\Users\\Hutto\\PycharmProjects\\loggerloader\\loggerloader'],
             binaries=[],
             datas=[('C:\\Users\\Hutto\\PycharmProjects\\loggerloader\\data_files\\', 'data_files'),
             ('C:\\ProgramData\\Anaconda3\\envs\\loaderlib\\Library\\bin\\','.')],
             hiddenimports=['pysqlite2',],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
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
