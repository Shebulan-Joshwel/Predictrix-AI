"""
Terminal output theming for the agent CLI. Ties visually to the same
dig/mining metaphor as the web UI, so the CLI and UI feel like one
consistent product for your demo video, not two disconnected pieces.

Also silences a known harmless dependency warning (a logfire/pydantic
plugin ImportError that fires on every run regardless of anything we do --
it's a version mismatch inside chromadb's dependencies, not our code, and
doesn't affect functionality) so your terminal output stays clean.
"""

import sys
import time
import threading
import warnings

warnings.filterwarnings("ignore")  # suppress the harmless logfire/pydantic warning

from colorama import init as colorama_init, Fore, Style
colorama_init(autoreset=True)


def header(text: str):
    bar = "=" * (len(text) + 4)
    print(f"\n{Fore.CYAN}{bar}")
    print(f"{Fore.CYAN}  {text}")
    print(f"{Fore.CYAN}{bar}{Style.RESET_ALL}")


def iteration_label(n: int):
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}--- LAYER {n} " + "-" * 32 + Style.RESET_ALL)


def thought(text: str):
    print(f"{Fore.WHITE}  thought:{Style.RESET_ALL} {Style.DIM}{text}{Style.RESET_ALL}")


def search_query(query: str):
    print(f'{Fore.MAGENTA}  digging for: "{query}"{Style.RESET_ALL}')


def draft_answer(text: str):
    print(f"{Fore.WHITE}  draft answer:{Style.RESET_ALL} {text}")


def answer(text: str, confidence: str):
    color = Fore.GREEN if confidence == "high" else Fore.RED if confidence == "low" else Fore.YELLOW
    width = 52
    print(f"\n{Fore.CYAN}{'=' * width}")
    print(f"{Fore.CYAN}  ANSWER   {color}[{confidence.upper()} CONFIDENCE]{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * width}{Style.RESET_ALL}")
    print(f"  {Style.BRIGHT}{text}{Style.RESET_ALL}\n")


def conflict(summary: str):
    print(f"{Fore.RED}  \u26a0 conflict resolved:{Style.RESET_ALL} {summary}")


def info(text: str):
    print(f"{Fore.BLUE}{text}{Style.RESET_ALL}")


class Spinner:
    """
    Pixel-block spinner for the blocking waits (API calls). Runs in a
    background thread so a multi-second network call doesn't just look
    like a frozen terminal -- useful for a live demo recording especially.
    Usage: with Spinner("digging for evidence..."): <blocking call>
    """
    FRAMES = ["\u2591", "\u2592", "\u2593", "\u2588", "\u2593", "\u2592"]

    def __init__(self, message: str = "working..."):
        self.message = message
        self._running = False
        self._thread = None

    def _spin(self):
        i = 0
        while self._running:
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stdout.write(f"\r{Fore.YELLOW}  {frame} {self.message}{Style.RESET_ALL}   ")
            sys.stdout.flush()
            time.sleep(0.15)
            i += 1
        sys.stdout.write("\r" + " " * (len(self.message) + 15) + "\r")
        sys.stdout.flush()

    def __enter__(self):
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)