#!/usr/bin/env python3
"""Debt Tracker — Interactive Menu. Run: python3 menu.py"""

import subprocess, sys
from pathlib import Path

TRACKER = Path(__file__).parent / "tracker.py"
PY      = sys.executable

def run(*args):
    subprocess.run([PY, str(TRACKER)] + list(args))

def cls():
    print("\033[2J\033[H", end="")

def menu():
    while True:
        cls()
        print("\033[1m\033[96m")
        print("  ╔══════════════════════════════════════╗")
        print("  ║     💳  JAYVEE DEBT TRACKER          ║")
        print("  ╚══════════════════════════════════════╝\033[0m")
        print()
        print("  \033[93m── MONTHLY WORKFLOW (do in order) ──\033[0m")
        print("  1  Update SAR→PHP rate (manual input)")
        print("  2  Plan remittance → how much to send")
        print("  3  Export dashboard + AI analysis (opens browser)")
        print("  4  Record this month's payments")
        print()
        print("  \033[93m── VIEW & ANALYZE ──\033[0m")
        print("  5  Summary (latest month)")
        print("  6  Summary (pick a month)")
        print("  7  Full payoff timeline — Avalanche")
        print("  8  Full payoff timeline — Snowball")
        print("  9  Payoff strategy / priority order")
        print("  10 Balance history trend")
        print("  11 Budget planner (enter PHP amount)")
        print("  12 AI analysis only (terminal)")
        print()
        print("  \033[93m── SETUP ──\033[0m")
        print("  13 Save OpenAI API key")
        print()
        print("  0  Exit")
        print()

        choice = input("  Pick a number: ").strip()

        if choice == "0":
            print("\n  Bye!\n")
            break

        elif choice == "1":
            run("setrate")

        elif choice == "2":
            sar = input("\n  How much SAR sending this month? ").strip()
            if sar:
                run("remit", sar)

        elif choice == "3":
            run("export")

        elif choice == "4":
            run("add")

        elif choice == "5":
            run("summary")

        elif choice == "6":
            month = input("\n  Month (e.g. 2026-03): ").strip()
            run("summary", month) if month else run("summary")

        elif choice == "7":
            run("plan", "avalanche")

        elif choice == "8":
            run("plan", "snowball")

        elif choice == "9":
            method = input("\n  Strategy [avalanche/snowball] (Enter = avalanche): ").strip() or "avalanche"
            run("strategy", method)

        elif choice == "10":
            run("history")

        elif choice == "11":
            php = input("\n  PHP budget amount: ").strip()
            if php:
                run("budget", php)

        elif choice == "12":
            run("analyze")

        elif choice == "13":
            key = input("\n  Paste OpenAI API key (sk-...): ").strip()
            if key:
                run("setkey", key)

        else:
            print("\n  \033[91mInvalid choice.\033[0m")

        input("\n  Press Enter to go back to menu...")

if __name__ == "__main__":
    menu()
