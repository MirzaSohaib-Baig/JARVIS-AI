import subprocess

subprocess.run(["start", "opera", "--new-window", "https://www.google.com"], shell=True)  # or ['start', 'msedge', '--new-window', '{url}']