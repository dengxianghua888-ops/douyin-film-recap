import json
from typer.testing import CliRunner
from douyin_film_recap.cli import app


def test_narration_plan_cli_is_read_only(tmp_path,monkeypatch):
    import douyin_film_recap.narration_revision as revision
    request=tmp_path/'request.json'
    request.write_text(json.dumps({'base':{'generation':'g'},'edits':{'vo1':'精确新句子'}}))
    calls=[]
    monkeypatch.setattr(revision,'prepare_narration_revision',lambda *a,**kw:calls.append(kw) or {'status':'PENDING_TTS'})
    result=CliRunner().invoke(app,['narration-revise-plan',str(tmp_path),'--request',str(request)])
    assert result.exit_code==0,result.output
    assert calls==[{'base':{'generation':'g'},'edits':{'vo1':'精确新句子'},'reason':''}]
    assert json.loads(result.stdout)['status']=='PENDING_TTS'


def test_narration_execute_defaults_to_no_new_remote_or_render(tmp_path,monkeypatch,app_config):
    import douyin_film_recap.cli as cli
    import douyin_film_recap.narration_revision as revision
    plan=tmp_path/'plan.json';plan.write_text('{}')
    seen=[]
    monkeypatch.setattr(cli,'load_config',lambda path:app_config)
    monkeypatch.setattr(revision,'execute_narration_revision',lambda *a,**kw:seen.append(kw) or {'status':'ADOPTED'})
    result=CliRunner().invoke(app,['narration-revise-apply',str(tmp_path),'--plan',str(plan)])
    assert result.exit_code==0,result.output
    assert seen[0]['allow_remote'] is False and seen[0]['render'] is False
    assert seen[0]['max_remote_requests'] is None


def test_narration_execute_forwards_explicit_scope(tmp_path,monkeypatch,app_config):
    import douyin_film_recap.cli as cli
    import douyin_film_recap.narration_revision as revision
    plan=tmp_path/'plan.json';plan.write_text('{}')
    seen=[]
    monkeypatch.setattr(cli,'load_config',lambda path:app_config)
    monkeypatch.setattr(revision,'execute_narration_revision',lambda *a,**kw:seen.append(kw) or {'status':'ADOPTED'})
    result=CliRunner().invoke(app,['narration-revise-apply',str(tmp_path),'--plan',str(plan),
                                  '--allow-remote','--max-remote-requests','1','--render'])
    assert result.exit_code==0,result.output
    assert seen[0]['allow_remote'] is True and seen[0]['render'] is True
    assert seen[0]['max_remote_requests']==1
