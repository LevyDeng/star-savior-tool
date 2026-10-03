"""Windows window discovery and visible client-area capture."""
import ctypes
import os
from ctypes import wintypes

if os.name == 'nt':
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]


def enable_dpi_awareness():
    if os.name == 'nt':
        try:
            user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except AttributeError:
            pass


def list_windows():
    if os.name != 'nt':
        return []
    results = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def collect(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                text = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, text, length + 1)
                results.append((int(hwnd), text.value))
        return True

    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows(collect, 0)
    return sorted(results, key=lambda item: item[1].casefold())


def activate(hwnd):
    if os.name != 'nt' or not user32.IsWindow(hwnd):
        raise RuntimeError('所选窗口已关闭或不可用。')
    if user32.IsIconic(hwnd):
        raise RuntimeError('请先还原游戏窗口，然后再截图。')
    user32.SetForegroundWindow(hwnd)


def capture(hwnd, region=None):
    from PIL import ImageGrab
    if not user32.IsWindow(hwnd) or user32.IsIconic(hwnd):
        raise RuntimeError('游戏窗口已关闭或最小化。')
    if user32.GetForegroundWindow() != hwnd:
        raise RuntimeError('请将所选游戏窗口置于最前方后重试。')
    rect, point = wintypes.RECT(), wintypes.POINT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)) or not user32.ClientToScreen(hwnd, ctypes.byref(point)):
        raise ctypes.WinError(ctypes.get_last_error())
    width, height = rect.right, rect.bottom
    if width <= 0 or height <= 0:
        raise RuntimeError('所选窗口没有可截图的区域。')
    left, top, right, bottom = region or (0, 0, 1, 1)
    bounds = (point.x + round(width * left), point.y + round(height * top),
              point.x + round(width * right), point.y + round(height * bottom))
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        raise RuntimeError('请框选更大的事件区域。')
    return ImageGrab.grab(bbox=bounds, all_screens=True).convert('RGB')
