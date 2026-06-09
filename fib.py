"""
Kosztowny rekurencyjny Fibonacci — do testowania dystrybucji tasków.
Uruchomienie: python3 fib.py [n]   (domyślnie n=38)
"""
import sys
import time
import socket


def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 38
    print(f"[{socket.gethostname()}] computing fib({n})...")
    t0 = time.perf_counter()
    result = fib(n)
    elapsed = time.perf_counter() - t0
    print(f"fib({n}) = {result}  [{elapsed:.2f}s]")


if __name__ == "__main__":
    main()
