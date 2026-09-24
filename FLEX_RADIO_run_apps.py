"""Run the WSJT-X spot bridge and APRS beacon together."""

from pathlib import Path
import subprocess
import sys


APP_DIR = Path(__file__).resolve().parent
SCRIPTS = (
	APP_DIR / "wsjtx_spots_V2.py",
	APP_DIR / "FLEX_RADIO_aprs.py",
)


def start_script(script_path):
	"""Start a child script in this project's directory."""
	return subprocess.Popen(
		[sys.executable, str(script_path)],
		cwd=APP_DIR,
	)


def stop_process(process):
	if process.poll() is None:
		process.terminate()
		try:
			process.wait(timeout=5)
		except subprocess.TimeoutExpired:
			process.kill()
			process.wait()


def main():
	missing = [str(path.name) for path in SCRIPTS if not path.is_file()]
	if missing:
		raise FileNotFoundError(f"Missing script(s): {', '.join(missing)}")

	processes = []
	try:
		for script_path in SCRIPTS:
			print(f"Starting {script_path.name}...", flush=True)
			processes.append(start_script(script_path))

		# WSJT-X is the long-running process. Keep the launcher alive while
		# it runs and still notice if it exits unexpectedly.
		wsjtx_process = processes[0]
		return_code = wsjtx_process.wait()
		print(f"{SCRIPTS[0].name} exited with code {return_code}.")
	except KeyboardInterrupt:
		print("Stopping applications...")
	finally:
		for process in processes:
			stop_process(process)


if __name__ == "__main__":
	main()
