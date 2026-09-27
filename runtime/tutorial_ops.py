"""Explicit screen framing and evidence-window compilation, without UI interpretation."""
import re
from fractions import Fraction


def rectangle(value, width, height):
    from editing_runtime import exact_keys, require
    exact_keys(value, ['x', 'y', 'width', 'height'], ['x', 'y', 'width', 'height'])
    require(all(type(v) is int for v in value.values()), 'INTEGER_RECTANGLE_REQUIRED')
    x, y, w, h = (value[k] for k in ['x', 'y', 'width', 'height'])
    require(x >= 0 and y >= 0 and w > 0 and h > 0 and x+w <= width and y+h <= height,
            'RECTANGLE_OUT_OF_FRAME')
    return x, y, w, h


def screen_focus(request, directory, tools):
    from editing_runtime import exact_keys, require, source, span, write_json
    exact_keys(request, ['operation', 'source', 'crop', 'output', 'highlights'],
               ['operation', 'source', 'crop', 'output', 'highlights'])
    asset = source(request['source']); media = tools.probe(asset['path'])
    video = next((s for s in media['streams'] if s['codec_type'] == 'video'), None)
    require(video is not None, 'VIDEO_STREAM_REQUIRED')
    rotations = [video.get('tags', {}).get('rotate', 0)] + [s.get('rotation', 0) for s in video.get('side_data_list', [])]
    require(all(float(r) % 360 == 0 for r in rotations), 'ROTATED_COORDINATES_UNSUPPORTED')
    require(video.get('sample_aspect_ratio', '1:1') in ['1:1', '0:1', 'N/A'], 'NONSQUARE_PIXEL_COORDINATES_UNSUPPORTED')
    x, y, w, h = rectangle(request['crop'], video['width'], video['height'])
    require(all(v % 2 == 0 for v in [x,y,w,h]), 'EVEN_CROP_REQUIRED')
    output=request['output'];exact_keys(output, ['width','height'], ['width','height'])
    require(all(type(v) is int and 2 <= v <= 8192 and v % 2 == 0 for v in output.values()), 'EVEN_DIMENSION_REQUIRED')
    require(w*output['height'] == h*output['width'], 'OUTPUT_ASPECT_MUST_MATCH_CROP')
    require(isinstance(request['highlights'],list), 'HIGHLIGHTS_ARRAY_REQUIRED')
    filters=[f'crop={w}:{h}:{x}:{y}']
    for item in request['highlights']:
        exact_keys(item,['start','end','box','color_rgb','thickness'],['start','end','box','color_rgb','thickness'])
        a,b=span(item['start'],item['end'],media['duration'])
        hx,hy,hw,hh=rectangle(item['box'],video['width'],video['height'])
        require(hx>=x and hy>=y and hx+hw<=x+w and hy+hh<=y+h,'HIGHLIGHT_OUTSIDE_CROP')
        require(isinstance(item['color_rgb'],str) and re.fullmatch('[0-9A-Fa-f]{6}',item['color_rgb']),'COLOR_RGB_REQUIRED')
        t=item['thickness'];require(type(t) is int and 1<=t<=min(hw,hh)//2,'THICKNESS_INVALID')
        filters.append(f"drawbox=x={hx-x}:y={hy-y}:w={hw}:h={hh}:color=0x{item['color_rgb']}:t={t}:enable='gte(t,{a})*lt(t,{b})'")
    filters.extend([f"scale={output['width']}:{output['height']}",'setsar=1'])
    tools.ff(['-i',asset['path'],'-vf',','.join(filters),'-map','0:v:0','-map','0:a?',
              '-c:v','libx264','-crf','18','-preset','medium','-c:a','copy',str(directory/'focused.mp4')])
    actual=tools.probe(directory/'focused.mp4')
    require(abs(actual['duration']-media['duration'])<=0.1,'FOCUS_DURATION_CHANGED')
    report={'source':asset,'crop':request['crop'],'output':output,'highlights':request['highlights'],
            'time_mapping':'output seconds equal source seconds; no time edit',
            'coordinate_mapping':{'offset_x':x,'offset_y':y,'scale_x':output['width']/w,'scale_y':output['height']/h},
            'semantic_target_check':'NOT_RUN','legibility_check':'NOT_RUN','audio':'stream copy, when present'}
    write_json(directory/'focus-map.json',report)
    return report


def compile_tutorial(request, directory, tools):
    from editing_runtime import exact_keys, require, normalize_plan, fingerprint, number, span, source, write_json
    exact_keys(request,['operation','plan','expected_revision','steps','result_cues'],
               ['operation','plan','expected_revision','steps','result_cues'])
    plan=request['plan']
    require(fingerprint(plan)==request['expected_revision'],'PLAN_REVISION_CONFLICT')
    normalized=normalize_plan(plan,tools)
    require(isinstance(request['steps'],list) and request['steps'],'STEPS_REQUIRED')
    require(isinstance(request['result_cues'],list),'RESULT_CUES_REQUIRED')
    clips={c['id']:c for c in normalized['clips']}; mapped=[]; ids=set()
    for step in request['steps']:
        exact_keys(step,['id','label','context_id','requires','before','action','result'],
                   ['id','label','context_id','requires','before','action','result'])
        sid=step['id']
        require(isinstance(sid,str) and sid and sid not in ids,'STEP_ID_DUPLICATE_OR_EMPTY');ids.add(sid)
        require(all(isinstance(step[k],str) and step[k].strip() for k in ['label','context_id']),'STEP_CONTEXT_REQUIRED')
        require(isinstance(step['requires'],list) and all(isinstance(x,str) for x in step['requires']),'STEP_DEPENDENCIES_REQUIRED')
        require(len(set(step['requires']))==len(step['requires']),'DUPLICATE_DEPENDENCY')
        result={'id':sid,'label':step['label'],'context_id':step['context_id'],'requires':step['requires']}
        source_ids=set(); previous_source_end=-1; previous_output_end=-1
        for role in ['before','action','result']:
            event=step[role]
            exact_keys(event,['clip_id','start','end','min_visible_seconds','evidence'],
                       ['clip_id','start','end','min_visible_seconds','evidence'])
            require(event['clip_id'] in clips,'EVENT_CLIP_UNKNOWN')
            clip=clips[event['clip_id']];source_ids.add(clip['source_id'])
            require(len(source_ids)==1,'STEP_MUST_USE_ONE_CAPTURE_SOURCE')
            media=normalized['sources'][clip['source_id']]['media']
            a,b=span(event['start'],event['end'],media['duration'])
            mapping=clip['source_to_output_map']
            visible_end=min(clip['effective_source_end'],mapping['source_end'])
            require(mapping['source_start']<=a and b<=visible_end+1e-8,
                    'EVENT_NOT_FULLY_VISIBLE: '+sid+'/'+role)
            speed=float(Fraction(mapping['source_seconds_per_output_second']))
            start=mapping['output_start']+(a-mapping['source_start'])/speed
            end=mapping['output_start']+(b-mapping['source_start'])/speed
            require(end<=mapping['output_end']+1e-8,'EVENT_NOT_FULLY_VISIBLE: '+sid+'/'+role)
            hold=number(event['min_visible_seconds'],'min_visible_seconds',0)
            require(hold>0 and end-start+1e-8>=hold,'READING_WINDOW_TOO_SHORT: '+sid+'/'+role)
            require(a>=previous_source_end-1e-8 and start>=previous_output_end-1e-8,'STEP_CAUSAL_ORDER_VIOLATION: '+sid)
            previous_source_end=b;previous_output_end=end
            evidence=source(event['evidence'])
            result[role]={'clip_id':clip['id'],'source_id':clip['source_id'],'source_start':a,'source_end':b,
                          'output_start':start,'output_end':end,'min_visible_seconds':hold,'evidence':evidence}
        mapped.append(result)
    by_id={s['id']:s for s in mapped}
    for step in mapped:
        for dep in step['requires']:
            require(dep in by_id and dep!=step['id'],'STEP_DEPENDENCY_UNKNOWN_OR_SELF')
            parent=by_id[dep]
            require(parent['context_id']==step['context_id'],'DEPENDENCY_CONTEXT_MISMATCH')
            require(parent['result']['output_end']<=step['action']['output_start']+1e-8,'STEP_DEPENDENCY_ORDER_VIOLATION')
    # Positive event durations plus strict temporal progression also rule out dependency cycles.
    cue_ids=set();cues=[]
    for cue in request['result_cues']:
        exact_keys(cue,['id','step_id','start','end','text'],['id','step_id','start','end','text'])
        require(isinstance(cue['id'],str) and cue['id'] and cue['id'] not in cue_ids,'CUE_ID_DUPLICATE_OR_EMPTY');cue_ids.add(cue['id'])
        require(cue['step_id'] in by_id,'CUE_STEP_UNKNOWN')
        require(isinstance(cue['text'],str) and cue['text'].strip(),'CUE_TEXT_REQUIRED')
        a,b=span(cue['start'],cue['end'],normalized['duration']);event=by_id[cue['step_id']]['result']
        require(a>=event['output_start']-1e-8 and b<=event['output_end']+1e-8,'RESULT_CUE_OUTSIDE_EVIDENCE_WINDOW')
        cues.append(cue)
    write_json(directory/'execution-plan.json',plan)
    report={'schema':'tutorial-proof-map/1','plan_revision':fingerprint(plan),'steps':mapped,'result_cues':cues,
            'evidence_check':'hash and declared time coverage only; screenshots/logs not interpreted',
            'ui_fact_review':'NOT_RUN','instruction_reproducibility':'NOT_RUN','style_quality':'NOT_RUN',
            'scope':'declared events only; no automatic detection of omitted prerequisites or undisclosed result previews'}
    write_json(directory/'tutorial-proof-map.json',report)
    return report


def execute(request,directory,tools):
    if request['operation']=='screen-focus':return screen_focus(request,directory,tools)
    return compile_tutorial(request,directory,tools)
