"""Prevent auxiliary console processes from interrupting a windowed build."""
import inspect
import os
import subprocess
import sys


def install_windowed_process_policy():
    """Keep default child processes console-free in the frozen Windows app."""
    if os.name != 'nt' or not getattr(sys, 'frozen', False):
        return
    if getattr(subprocess.Popen, '_windowed_process_policy', False):
        return
    original = subprocess.Popen
    signature = inspect.signature(original)

    class WindowedPopen(original):
        _windowed_process_policy = True

        def __init__(self, *args, **kwargs):
            arguments = signature.bind(*args, **kwargs)
            flags = arguments.arguments.get('creationflags', 0)
            # Preserve callers that explicitly request a different console mode.
            if not flags & (subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS):
                flags |= subprocess.CREATE_NO_WINDOW
            arguments.arguments['creationflags'] = flags
            super().__init__(*arguments.args, **arguments.kwargs)

    subprocess.Popen = WindowedPopen
