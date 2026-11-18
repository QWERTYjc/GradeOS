"""Complete local OCR regions from source ink. No rubric, answers, or network.

Ruled sheets provide physical writing bands. Within each band, whitespace
separates independent blocks and smaller gaps retain disjoint highlight boxes.
Unruled areas retain their OCR geometry instead of guessing a writing grid.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def runs(indices, gap=1):
    result = []
    for value in indices:
        value = int(value)
        if result and value - result[-1][-1] <= gap:
            result[-1].append(value)
        else:
            result.append([value])
    return [(row[0], row[-1] + 1) for row in result]


def components(mask):
    """Run-length connected components, with no additional OCR/ML runtime."""
    parent=[];boxes=[];previous=[]
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for y,row in enumerate(mask):
        changes=np.diff(np.pad(row.astype(np.int8),(1,1)))
        starts=np.flatnonzero(changes==1);ends=np.flatnonzero(changes==-1)
        current=[];j=0
        for a,b in zip(starts,ends):
            a,b=int(a),int(b)
            while j<len(previous) and previous[j][1]<a:j+=1
            touched=[];k=j
            while k<len(previous) and previous[k][0]<=b:
                touched.append(root(previous[k][2]));k+=1
            if touched:
                target=min(touched)
                for other in touched:
                    if other==target:continue
                    parent[other]=target
                    box=boxes[other];dest=boxes[target]
                    boxes[target]=[min(dest[0],box[0]),min(dest[1],box[1]),max(dest[2],box[2]),max(dest[3],box[3]),dest[4]+box[4]]
                box=boxes[target];boxes[target]=[min(box[0],a),box[1],max(box[2],b),y+1,box[4]+b-a]
            else:
                target=len(parent);parent.append(target);boxes.append([a,y,b,y+1,b-a])
            current.append((a,b,target))
        previous=current
    return [box for i,box in enumerate(boxes) if root(i)==i and box[4]>=3]


def rules_and_ink(image):
    ink = np.asarray(image.convert('L')) < 190
    height, width = ink.shape
    radius = max(2, round(height * .0015))
    broad = ink.copy()
    for delta in range(1, radius + 1):
        broad[delta:] |= ink[:-delta]
        broad[:-delta] |= ink[delta:]
    candidates = runs(np.flatnonzero(broad.sum(axis=1) > width * .38), radius)
    centers = [(a + b) / 2 for a, b in candidates if b-a < height * .012]
    # Require repeated spacing, not isolated formula bars or table borders.
    differences = [b-a for a, b in zip(centers, centers[1:]) if height*.012 < b-a < height*.075]
    if len(differences) < 4:
        return [], ink
    period = float(np.median(differences))
    regular = [y for y in centers if sum(abs(abs(y-z)-period) < period*.12 for z in centers) >= 1]
    if len(regular) < 5:
        return [], ink
    # Dotted/tilted rules are removed from the analysis mask only. Source bytes
    # and the whole-page model/display images are never edited by this step.
    cleaned = ink.copy()
    for center in regular:
        a, b = max(0, int(center-radius-2)), min(height, int(center+radius+2))
        # Preserve vertical/diagonal glyph strokes crossing or ending on a
        # printed rule. Removing the entire strip would amputate denominators.
        near=ink[max(0,a-3):a].any(axis=0)|ink[b:min(height,b+3)].any(axis=0)
        support=near.copy()
        for delta in (1,2):
            support[delta:]|=near[:-delta];support[:-delta]|=near[delta:]
        cleaned[a:b] = ink[a:b]&support
    # Remove the vertical page border, using the same long-line criterion.
    vertical = ink.copy()
    for delta in range(1, max(2, round(width*.0015)) + 1):
        vertical[:, delta:] |= ink[:, :-delta]
        vertical[:, :-delta] |= ink[:, delta:]
    for a, b in runs(np.flatnonzero(vertical.sum(axis=0) > height*.6), 2):
        cleaned[:, max(0,a-2):min(width,b+2)] = False
    # Boundaries assign whole components, never cut their glyphs. Searching for
    # a later whitespace valley can drift into the first row of a matrix.
    boundaries = [int(center+period*.06) for center in regular]
    return boundaries, cleaned


def complete_regions(image, rows):
    width, height = image.size
    boundaries, ink = rules_and_ink(image)
    if not boundaries:
        return rows, {'mode': 'ocr-unruled', 'writing_bands': 0}
    typical = float(np.median(np.diff(boundaries)))
    for row in rows:
        x,y,w,h=row['rect']
        if h*height > max(typical*2,w*width*3):
            ink[max(0,int(y*height)-2):min(height,int((y+h)*height)+3),
                max(0,int(x*width)-2):min(width,int((x+w)*width)+3)] = False
    # Keep the first band above the first repeated rule as well.
    edges = [max(0, int(boundaries[0]-typical)), *boundaries]
    result, consumed = [], set()
    glyphs=components(ink)
    for top, bottom in zip(edges, edges[1:]):
        if bottom-top > typical*1.25:
            continue  # no invented rule across a missing or irregular interval
        seeds = []
        for index, row in enumerate(rows):
            x,y,w,h = row['rect']
            if h*height > typical*2 or w*width < 2:
                continue
            if top <= (y+h*.5)*height < bottom:
                seeds.append((index,row))
        if not seeds:
            continue
        band = np.zeros_like(ink[top:bottom])
        owned=[]
        for a,b,c,d,area in glyphs:
            cx,cy=(a+c)/2,(b+d)/2
            owners=[]
            for index,row in enumerate(rows):
                x,y,w,h=row['rect']
                if h*height<=typical*1.1 and x*width<=cx<=(x+w)*width and y*height<=cy<=(y+h)*height:
                    owners.append((abs(cy-(y+h/2)*height),index,(y+h/2)*height))
            owner_y=min(owners)[2] if owners else cy
            if top <= owner_y < bottom:
                owned.append((a,b,c,d))
                start,end=max(top,b),min(bottom,d)
                if start<end:
                    band[start-top:end-top,a:c]|=ink[start:end,a:c]
                else:
                    at=max(0,min(bottom-top-3,int(owner_y-top)))
                    band[at:at+3,a:c]|=ink[b:d,a:c].any(axis=0)
        # A neighboring short OCR observation owns its glyphs even if a
        # descender, matrix cell, or superscript crosses the printed baseline.
        # Tall OCR boxes spanning several rows are deliberately not authority.
        for index,row in enumerate(rows):
            if index in {i for i,_ in seeds}:
                continue
            x,y,w,h=row['rect']
            if h*height < typical*1.1:
                a,b=max(top,int(y*height)),min(bottom,int((y+h)*height)+1)
                if a<b:band[a-top:b-top,max(0,int(x*width)):min(width,int((x+w)*width)+1)]=False
        # Suppress isolated scan dust. No character-recognition assumptions.
        active = np.flatnonzero(band.sum(axis=0) >= max(2, int((bottom-top)*.035)))
        blocks = runs(active, max(3, round(width*.14)))
        for left, right in blocks:
            owners = [(i,r) for i,r in seeds if r['rect'][0]*width < right
                      and (r['rect'][0]+r['rect'][2])*width > left]
            if not owners:
                continue
            pieces = []
            for x1,x2 in runs(active[(active >= left) & (active < right)], max(3, round(width*.035))):
                yy,xx = np.nonzero(band[:,x1:x2])
                if len(yy) < 5:
                    continue
                # Pad only the source-pixel measurement, never an entire band.
                pad = max(2, round(height*.001))
                a,b = max(0,x1+int(xx.min())-pad), min(width,x1+int(xx.max())+pad+1)
                c,d = max(0,top+int(yy.min())-pad), min(height,top+int(yy.max())+pad+1)
                for ga,gb,gc,gd in owned:
                    if ga<b and gc>a:
                        c=min(c,max(0,gb-pad));d=max(d,min(height,gd+pad))
                for _,row in owners:
                    ox,oy,ow,oh=row['rect']
                    if oh*height <= typical*1.1 and ox*width < b and (ox+ow)*width > a:
                        c=min(c,max(0,int(oy*height)-pad))
                        d=max(d,min(height,int((oy+oh)*height)+pad+1))
                pieces.append([a/width,c/height,(b-a)/width,(d-c)/height])
            if not pieces:
                continue
            x1=min(p[0] for p in pieces); y1=min(p[1] for p in pieces)
            x2=max(p[0]+p[2] for p in pieces); y2=max(p[1]+p[3] for p in pieces)
            owners.sort(key=lambda p: (p[1]['rect'][0],p[1]['rect'][1]))
            text = ' | '.join(r.get('candidates',[{}])[0].get('text','') for _,r in owners)
            result.append({'rect':[x1,y1,x2-x1,y2-y1], 'rects':pieces,
                           'candidates':[{'text':text,'confidence':None}],
                           'ocr_rows':[i for i,_ in owners], 'geometry':'local-ink-writing-band'})
            consumed.update(i for i,_ in owners)
    # The non-ruled question/header areas and vertical notices are unchanged.
    result.extend({**row,'ocr_rows':[i],'geometry':'local-ocr'} for i,row in enumerate(rows) if i not in consumed)
    return result, {'mode':'local-ocr+ink-writing-bands','writing_bands':len(boundaries)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--documents',required=True,type=Path)
    parser.add_argument('--observations',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    documents=json.loads(args.documents.read_text())
    observed=json.loads(args.observations.read_text())
    for key,document in documents.items():
        target=observed['documents'][key]
        if target['source_sha256'] != document['sha256']:
            raise ValueError('OCR document binding mismatch')
        for page in document['pages']:
            source=next(p for p in target['pages'] if p['page']==page['page'])
            if source['source_sha256'] != page['sha256'] or hashlib.sha256(Path(page['absolute_path']).read_bytes()).hexdigest()!=page['sha256']:
                raise ValueError('OCR geometry source changed')
            with Image.open(page['absolute_path']) as image:
                source['rows'],source['geometry_analysis']=complete_regions(image,source['rows'])
    observed['geometry_version']=1
    observed['geometry_engine']='local source-ink writing bands; no model coordinates'
    args.output.write_text(json.dumps(observed,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    main()
