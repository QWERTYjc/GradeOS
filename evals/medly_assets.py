"""The existing 173-answer GradeOS Medly source snapshot, without examiner labels."""
from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

from evals.fixture_inputs import sha, prepare

ROOT = Path(__file__).resolve().parent / 'medly'
FIELDS = {'answer_id', 'question_id', 'subject', 'modality', 'answer_file', 'question_file', 'question_image_file'}


def asset(path: str) -> Path:
    target = (ROOT / path).resolve()
    if not target.is_relative_to((ROOT / 'sources').resolve()) or not target.is_file():
        raise ValueError('Medly asset outside declared source directory')
    return target


def check() -> list[dict]:
    inventory = json.loads((ROOT / 'assets.json').read_text())
    if sha(ROOT / 'inputs.jsonl') != inventory['inputs_sha256']:
        raise ValueError('Medly input manifest changed')
    for path, digest in inventory['files'].items():
        if sha(asset(path)) != digest:
            raise ValueError('Medly source hash mismatch')
    rows = [json.loads(line) for line in (ROOT / 'inputs.jsonl').read_text().splitlines()]
    if len(rows) != inventory['input_count'] or len({r['answer_id'] for r in rows}) != len(rows):
        raise ValueError('Medly inventory count mismatch')
    for row in rows:
        if set(row) != FIELDS:
            raise ValueError('Unexpected fields in score-blind Medly input')
        for field in ['answer_file', 'question_file', 'question_image_file']:
            if row[field]:
                asset(row[field])
        question = json.loads(asset(row['question_file']).read_text())
        if question['question_id'] != row['question_id'] or set(question) - {
            'question_id', 'markmax', 'question_stem', 'question_text', 'markscheme', 'question_image'
        }:
            raise ValueError('Unexpected question source fields')
    return rows


def prepare_answer(answer_id: str, output: Path) -> dict:
    from PIL import Image
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from pypdf import PdfReader
    from scripts.python.annotation_pdf import register_font

    row = next((r for r in check() if r['answer_id'] == answer_id), None)
    if row is None:
        raise ValueError('Unknown Medly answer; inspect evals/medly/inputs.jsonl')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'
    source.mkdir()
    question = json.loads(asset(row['question_file']).read_text())
    style = ParagraphStyle('source', fontName=register_font(), fontSize=11, leading=16)
    content = []
    for label, text in [('Question', question['question_stem']), ('Question text', question['question_text']),
                        ('Maximum', str(question['markmax'])), ('Mark scheme', question['markscheme'])]:
        content.extend([Paragraph(escape(label), style),
                        Paragraph(escape(text).replace('\n', '<br/>'), style), Spacer(1, 14)])
    SimpleDocTemplate(str(source / 'scheme.pdf')).build(content)

    def image_pdf(image_path: Path, target: Path):
        with Image.open(image_path) as image:
            page = canvas.Canvas(str(target), pagesize=image.size)
            page.drawImage(ImageReader(image), 0, 0, width=image.width, height=image.height)
            page.showPage()
            page.save()

    image_pdf(asset(row['answer_file']), source / 'student.pdf')
    roles = ['scheme', 'student']
    if row['question_image_file']:
        image_pdf(asset(row['question_image_file']), source / 'question.pdf')
        roles.append('question')
        # A referenced diagram belongs in the scheme packet too, so the CLI cannot omit it.
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.append(source / 'scheme.pdf')
        writer.append(source / 'question.pdf')
        with (source / 'scheme-with-diagram.pdf').open('wb') as handle:
            writer.write(handle)
        (source / 'scheme-with-diagram.pdf').replace(source / 'scheme.pdf')
    documents = {}
    for role in roles:
        path = source / f'{role}.pdf'
        count = len(PdfReader(path).pages)
        documents[role] = {'path': path.name, 'sha256': sha(path), 'page_count': count, 'pages': list(range(1, count + 1))}
    (source / 'input.json').write_text(json.dumps({'version': 1, 'documents': documents}, indent=2) + '\n')
    result = prepare(source, output / 'prepared')
    (output / 'provenance.json').write_text(json.dumps({
        'answer_id': answer_id, 'source_files': {r: sha(asset(row[r])) for r in
            ['answer_file', 'question_file', 'question_image_file'] if row[r]},
        'rendering': 'Original scan pixels embedded; source text printed verbatim, including literal LaTeX.',
        'reference_labels': 'unavailable in this snapshot',
    }, indent=2) + '\n')
    return result
