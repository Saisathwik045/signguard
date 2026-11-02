"""Trusted subprocess launcher: OS rlimits are defense-in-depth, not network/filesystem isolation."""
import os
import resource
import sys


def main():
    cpu, memory, output = map(int, sys.argv[1:4])
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_FSIZE, (output, output))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    os.execv(sys.argv[4], sys.argv[4:])


if __name__ == "__main__":
    main()
