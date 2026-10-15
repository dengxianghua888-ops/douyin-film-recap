import json
from pathlib import Path
import tempfile
import unittest
from douyin_film_recap.workspace import inventory

class CacheRecoveryReferencesTests(unittest.TestCase):
    def test_published_board_refs_survive_before_stage_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'state.json').write_text(json.dumps({'schema_version':2,'stages':{'render':{'status':'running'}}}))
            attempt=root/'render_attempts'/'fixture'/'output';attempt.mkdir(parents=True)
            refs={}
            for name in ('render_plan','render_receipt'):
                path=attempt/(name+'.json');path.write_text('{}');refs[name]=str(path)
            (root/'09_storyboard.json').write_text(json.dumps({'output':refs}))
            disposable=root/'render_cache';disposable.mkdir();(disposable/'unused.mp4').write_bytes(b'cache')
            rows,_,_=inventory(root)
            names={row['path'] for row in rows}
            for name in ('render_plan','render_receipt'):
                self.assertIn('render_attempts/fixture/output/'+name+'.json',names)
            self.assertNotIn('render_cache/unused.mp4',names)

if __name__=='__main__':unittest.main()
