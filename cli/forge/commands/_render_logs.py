def print_run_logs(run: dict):
    commit = run.get("commit", "")[:7]
    message = run.get("message") or "(no commit message)"
    status = run.get("status", "unknown")
    created = run.get("created_at", "")
    logs = run.get("logs") or {}

    print("")
    print(f"Run {run['id']}")
    print("-" * 72)
    print(f"Commit     {commit}  {message}")
    print(f"Status     {status}")
    print(f"Created    {created}")
    print("")

    steps = logs.get("steps", [])

    if not steps:
        print("No logs available for this run.")
        return

    print("Steps")
    print("-" * 72)

    for idx, step in enumerate(steps, start=1):
        print(f"[{idx}] {step['name']}")
        print(f"Command:")
        print(f"  {step.get('command', '(unknown)')}")
        print("")

        if step.get("stdout"):
            print("Output:")
            for line in step["stdout"].splitlines():
                print(f"  {line}")

        if step.get("stderr"):
            print("Error:")
            for line in step["stderr"].splitlines():
                print(f"  {line}")

        print("")
        print(
            f"Result     {step['status']} "
            f"({step.get('duration_ms', 0)} ms)"
        )
        print("")
