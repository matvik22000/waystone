import datetime
import os
import platform


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def get_process_rss_bytes() -> int | None:
    """
    Return current process RSS in bytes when available.
    On Windows, return None as requested.
    """
    if platform.system().lower().startswith("win"):
        return None

    # Linux and most Unix-like systems with /proc support.
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as f:
            parts = f.read().strip().split()
        if len(parts) >= 2:
            rss_pages = int(parts[1])
            page_size = os.sysconf("SC_PAGE_SIZE")
            return rss_pages * page_size
    except Exception:
        pass

    # Fallback for Unix systems; note ru_maxrss may be peak RSS.
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_kb = int(usage.ru_maxrss)
        return rss_kb * 1024
    except Exception:
        return None
