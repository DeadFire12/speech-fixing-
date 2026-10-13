
"""Lily — local Win7-compatible merged assistant.

Default: Mark-LIV-inspired HUD + Lily's original local brain.
Console: python Lily.py --console
Self test: python Lily.py --selftest [--quick] [--audio]
Version:   python Lily.py --version
Status:    python Lily.py --status
"""
from __future__ import annotations
import argparse
import sys


def _make_console_safe():
    """Old Windows consoles (cp437/cp1252) raise UnicodeEncodeError on the emoji in some
    replies; replace what cannot be shown instead of crashing."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def main(argv=None):
    ap=argparse.ArgumentParser(description="Lily local AI assistant",formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--console",action="store_true",help="run the original Lily text console")
    ap.add_argument("--dashboard",action="store_true",help="start the Mark-LIV remote dashboard")
    ap.add_argument("--selftest",action="store_true",help="run Lily's diagnostics (PASS/WARNING/FAIL/SKIPPED) and exit")
    ap.add_argument("--quick",action="store_true",help="with --selftest: skip the live model test")
    ap.add_argument("--audio",action="store_true",help="with --selftest: also open the microphone briefly")
    import lily_version
    ap.add_argument("--version",action="version",version=lily_version.version_banner(),help="show Lily's version and exit")
    ap.add_argument("--status",action="store_true",help="show a quick health/status report and exit (read-only)")
    args=ap.parse_args(argv)
    _make_console_safe()
    if args.status:
        import lily_status
        return lily_status.main()
    # file logging (logs/lily.log) + a record of any crash, for every mode below
    import lily_log
    import lily_status
    lily_log.setup_logging()
    lily_log.install_excepthooks()
    log=lily_log.get_logger("main")
    mode="selftest" if args.selftest else ("console" if args.console else ("dashboard" if args.dashboard else "gui"))
    log.info("%s starting (mode=%s) | %s",lily_version.version_string(),mode,lily_version.runtime_summary())
    if args.selftest:
        import selftest
        return selftest.main(quick=args.quick, audio=args.audio)
    lily_status.mark_started(mode)
    try:
        return _run_mode(args,log)
    finally:
        lily_status.mark_stopped()
        log.info("Lily stopped (mode=%s)",mode)
        lily_log.shutdown_logging()


def _run_mode(args,log):
    if args.console:
        from lily_runtime import process_text
        print("Lily: Console mode. Type 'quit' to exit.")
        try:
            while True:
                try: user=input("You: ")
                except (EOFError,KeyboardInterrupt): print(); break
                if user.strip().lower() in ("quit","exit","bye","goodbye"): break
                import contextlib,io
                buf=io.StringIO()
                with contextlib.redirect_stdout(buf):
                    process_text(user, "local")
                out=buf.getvalue()
                print(out, end='' if out.endswith('\n') else '\n')
        finally:
            try:
                from core import local_engine
                local_engine.shutdown()
            except Exception:
                pass
        return 0
    from lily_gui import run_gui
    return run_gui(start_dashboard=args.dashboard)

if __name__=="__main__":
    raise SystemExit(main())
