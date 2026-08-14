def test_dump():
    from serve import app
    paths = sorted({getattr(r,"path",None) for r in app.routes} - {None})
    print("TOTAL_ROUTES=", len(paths))
    print("NOTEBOOK=", [p for p in paths if "notebook" in p])
    print("ONBOARDING=", [p for p in paths if "onboard" in p])
    print("SAMPLE=", paths[:8])
