from pathlib import Path
from streamlit.testing.v1 import AppTest


def click(app,label):
    next(b for b in app.button if b.label==label).click()
    return app.run(timeout=30)


def test_web_workflow_and_reload(tmp_path,monkeypatch):
    monkeypatch.setenv("PGE_AGENT_DATA_DIR",str(tmp_path))
    app=AppTest.from_file(str(Path(__file__).parents[1]/"app.py"))
    app.run(timeout=30)
    assert not app.exception
    click(app,"Load demonstration")
    assert not app.exception
    click(app,"Generate and save report")
    assert not app.exception
    assert app.session_state.current
    first=app.session_state.current
    next(t for t in app.text_input if t.label=="Structures").set_value("11")
    click(app,"Save reviewed inputs")
    assert not app.exception
    click(app,"Generate and save report")
    assert not app.exception
    assert app.session_state.current!=first
    from pge_agent.storage import RunStore
    latest=RunStore(tmp_path).get(app.session_state.current)
    assert latest.forecast.hours.total is None
    assert latest.parent_run_id==first
    reloaded=AppTest.from_file(str(Path(__file__).parents[1]/"app.py")).run(timeout=30)
    click(reloaded,"Open saved run")
    assert not reloaded.exception
    assert reloaded.session_state.current==latest.run_id
