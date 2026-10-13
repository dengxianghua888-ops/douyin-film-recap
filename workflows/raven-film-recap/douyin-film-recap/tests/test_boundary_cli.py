import json
from typer.testing import CliRunner
from douyin_film_recap.cli import app


def test_boundary_cli_obtains_independent_current_clock(tmp_path, monkeypatch, app_config):
    import douyin_film_recap.cli as cli
    import douyin_film_recap.boundary_apply as apply
    from douyin_film_recap.boundary import BoundaryProposal
    (tmp_path/'00_source_manifest.json').write_text(json.dumps({'sources':[], 'config_fingerprint':'fixture'}))
    request=tmp_path/'request.json'
    request.write_text(json.dumps({'proposal':{'untrusted_clock':'proposal'},'base':{'generation':'g'}}))
    calls=[]
    current={'verified_current_clock':'from-source-probe'}
    monkeypatch.setattr(cli,'load_config',lambda path:app_config)
    monkeypatch.setattr(BoundaryProposal,'model_validate',lambda value: value)
    monkeypatch.setattr(apply,'collect_boundary_timebases',lambda manifest:calls.append('probe') or current)
    def adopt(root,**kwargs):
        calls.append('apply')
        assert kwargs['timebases'] is current
        assert kwargs['base']=={'generation':'g'}
        return {'status':'ADOPTED'}
    monkeypatch.setattr(apply,'apply_boundary_proposal',adopt)
    result=CliRunner().invoke(app,['apply-boundary',str(tmp_path),'--proposal',str(request)])
    assert result.exit_code==0,result.output
    assert calls==['probe','apply']


def test_boundary_cli_rejects_caller_injected_current_clock(tmp_path):
    request=tmp_path/'request.json'
    request.write_text(json.dumps({'proposal':{},'base':{},'timebases':{'fake':'verified'}}))
    result=CliRunner().invoke(app,['apply-boundary',str(tmp_path),'--proposal',str(request)])
    assert result.exit_code==2
    assert 'INVALID_BOUNDARY_APPLICATION_REQUEST' in result.output
