import json, subprocess, sys, os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO, "skills", "seller-churn-assessment", "scripts", "run_pipeline.py")

def test_run_pipeline_missing_glid():
    """Script exits 1 and returns partial error JSON when no glid given."""
    result = subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data.get("_partial") is True
    assert "error" in data

def test_run_pipeline_invalid_glid():
    """Script exits 1 and returns partial error JSON for non-integer glid."""
    result = subprocess.run(
        [sys.executable, SCRIPT, "not_a_number"],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data.get("_partial") is True

def test_run_pipeline_tier_map():
    """map_tiers() converts Red->Critical, Amber->High, Green->Low."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_pipeline", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    result = mod.map_tiers({
        "final_tier": "Red",
        "phases": {
            "phase2": {
                "churn-scoring": {"data": {"risk": "Amber"}}
            }
        }
    })
    assert result["phases"]["phase2"]["churn-scoring"]["data"]["risk"] == "High"
    assert mod.map_tiers({"risk": "Green"})["risk"] == "Low"
    assert mod.map_tiers({"risk": "Unknown"})["risk"] == "Unknown"
