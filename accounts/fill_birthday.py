import pyperclip, pyautogui, time, win32gui, win32con

pyautogui.FAILSAFE = False

def focus_chrome():
    result = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h)
            if 'Google' in t or 'Chrome' in t:
                result.append(h)
    win32gui.EnumWindows(cb, None)
    if result:
        win32gui.SetForegroundWindow(result[0])
        time.sleep(0.5)
        return True
    return False

focus_chrome()
time.sleep(0.8)

# JavaScript to fill the birthday/gender form
js = (
    'var m=document.querySelector("#month");'
    'if(m){m.value="3";m.dispatchEvent(new Event("change",{bubbles:true}));}'
    'var nv=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value");'
    'var d=document.querySelector("#day");'
    'if(d){nv.set.call(d,"17");d.dispatchEvent(new Event("input",{bubbles:true}));}'
    'var y=document.querySelector("#year");'
    'if(y){nv.set.call(y,"1995");y.dispatchEvent(new Event("input",{bubbles:true}));}'
    'var g=document.querySelector("#gender");'
    'if(g){g.value="1";g.dispatchEvent(new Event("change",{bubbles:true}));}'
    '"Fields filled"'
)

pyperclip.copy(js)
print("JS copied to clipboard")

# Click in the DevTools console area
pyautogui.click(900, 371)
time.sleep(0.5)
pyautogui.hotkey('ctrl', 'a')
time.sleep(0.2)
pyautogui.hotkey('ctrl', 'v')
time.sleep(0.4)
pyautogui.press('enter')
time.sleep(1.5)
print("JS executed - fields should be filled")
