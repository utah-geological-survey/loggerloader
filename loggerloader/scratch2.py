import tkinter
from tkinter import *
from tkinter import filedialog
import xlrd

root = tkinter.Tk()
root.withdraw()


filename = filedialog.askopenfilename(title='Choose an excel file')
workbook = xlrd.open_workbook(filename)

master = Toplevel(root)
variable = StringVar(master)
variable.set(workbook.sheet_names()[0])
w = OptionMenu(*(master, variable) + tuple(workbook.sheet_names()))
w.pack()

mainloop()