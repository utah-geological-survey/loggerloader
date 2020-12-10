# -*- mode: python ; coding: utf-8 -*-
# use command pyinstaller --clean --onedir --distpath "C:/Users/Hutto/PycharmProjects/loggerloader/" C:/Users/Hutto/PycharmProjects/loggerloader/llguidir.spec


a = Analysis(['C:\\Users\\Hutto\\PycharmProjects\\loggerloader\\loggerloader\\llgui.py'],
             pathex=['C:\\Users\\Hutto\\PycharmProjects\\loggerloader\\loggerloader'],
             binaries=[],
             datas=[('C:\\Users\\Hutto\\PycharmProjects\\loggerloader\\data_files\\', 'data_files'),
             ('C:\\ProgramData\\Anaconda3\\envs\\loaderlib\\Library\\bin\\','.')],
             hiddenimports=['pkg_resources.py2_warn','pkg_resources.markers','babel.numbers','pysqlite2',
             'MySQLdb','sqlalchemy.sql.functions.func','mx.DateTime','System','copy_reg','setuptools.extern.six'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[])
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='loggerloaderdir',
          debug=True,
          bootloader_ignore_signals=False,
          console=True )
