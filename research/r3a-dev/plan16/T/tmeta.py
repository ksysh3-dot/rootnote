"""metadata.yaml stem table without PyYAML (regex, same style as common16.ref)"""
import re, os
FULL = '/mnt/d/rootnote-data/slakh2100/extracted/slakh2100_flac_redux/train'


def stems_meta(key):
    assert 'validation' not in key and 'test' not in key
    txt = open(f'{FULL}/{key}/metadata.yaml', encoding='utf-8', errors='replace').read()
    parts = re.split(r'\n\s{2}(S\d+):\s*\n', txt)
    have = set(os.listdir(f'{FULL}/{key}/stems'))
    out = {}
    for i in range(1, len(parts) - 1, 2):
        b = parts[i + 1]
        g = lambda name: (re.search(name + r':\s*(.*)', b) or [None, ''])[1].strip()
        out[parts[i]] = dict(cls=g('inst_class'), prog=g('midi_program_name'), pnum=g('program_num'), drum=bool(re.search(r'is_drum:\s*true', b)),
                             rendered=bool(re.search(r'audio_rendered:\s*true', b)), midi=bool(re.search(r'midi_saved:\s*true', b)), disk=(parts[i] + '.flac') in have)
    return out
