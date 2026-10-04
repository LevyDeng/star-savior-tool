"""Windows session-local singleton shared by source and packaged entry points."""
import ctypes
import os
from ctypes import wintypes

MUTEX_NAME = r'Local\StarSaviorTool.GuideDemo.SingleInstance.v1'


class SingleInstance:
    def __init__(self, name=MUTEX_NAME):
        self.name = name
        self.handle = None
        if os.name != 'nt':
            raise RuntimeError('Single-instance guard requires Windows')
        self.kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel32.CreateMutexW.restype = wintypes.HANDLE
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL

    def acquire(self):
        if self.handle is not None:
            return True
        ctypes.set_last_error(0)
        handle = self.kernel32.CreateMutexW(None, False, self.name)
        error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(error)
        if error == 183:
            self.kernel32.CloseHandle(handle)
            return False
        self.handle = handle
        return True

    def close(self):
        if self.handle is not None:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None
