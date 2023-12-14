import pyautogui as pa
import time

pa.PAUSE = 2
pa.press('win')
pa.write('chrome')
pa.press('ENTER')
pa.write('https://web.whatsapp.com/')
pa.press('ENTER')
time.sleep(15)
pa.hotkey('ctrl', 'alt', 'n')
time.sleep(5)
pa.write('Link')
pa.press('ENTER')