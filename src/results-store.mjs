import { mkdir, readFile } from 'node:fs/promises';
import { resolve, sep } from 'node:path';
import { digest } from './core.mjs';
import { freezeJson } from './cohort-runtime.mjs';

// Each child owns one immutable record. The index is committed only after all children settle.
export class ResultsStore {
  constructor(directory, studentIds, allowedRoots = [resolve(directory, '..')]) {
    if (!studentIds.length || new Set(studentIds).size !== studentIds.length || studentIds.some(id => !/^[A-Za-z0-9_-]{1,64}$/.test(id))) throw Error('Invalid result owners');
    this.directory = resolve(directory); this.ids = [...studentIds];
    this.roots = allowedRoots.map(root => resolve(root)); this.records = new Map(); this.sealed = null;
  }
  async init() { await mkdir(this.directory, { recursive: false }); }
  async publish(id, receipt) {
    if (!this.ids.includes(id) || this.records.has(id) || this.sealed) throw Error('Unknown, duplicate or sealed result owner');
    this.records.set(id, null); // Reserve before I/O; another writer cannot replace this student.
    try {
      if (!['submitted', 'failed', 'cancelled'].includes(receipt.status)) throw Error('Result is not terminal');
      const record = { student_id: id, ...structuredClone(receipt) };
      if (record.student_id !== id) throw Error('Result owner mismatch');
      if (record.status === 'submitted') {
        const grade = await this.loadGrade(record); await this.loadFeedback(record, grade);
      }
      await freezeJson(this.directory, `${id}.json`, record); this.records.set(id, record);
    } catch (error) { this.records.delete(id); throw error; }
  }
  async loadGrade(record) {
    const path = resolve(record.grading_path);
    if (!this.roots.some(root => path.startsWith(root + sep))) throw Error('Result outside authorized source roots');
    const bytes = await readFile(path);
    if (digest(bytes) !== record.grading_sha256) throw Error('Result content hash changed');
    const grade = JSON.parse(bytes.toString('utf8'));
    if (grade.rubric_hash !== record.rubric_hash) throw Error('Result rubric binding differs');
    return grade;
  }
  async loadFeedback(record, grade) {
    if (record.feedback_status !== 'submitted') return null;
    if (!record.feedback_path || !record.feedback_sha256) throw Error('Missing feedback receipt');
    const path = resolve(record.feedback_path);
    if (!this.roots.some(root => path.startsWith(root + sep))) throw Error('Feedback outside authorized source roots');
    const bytes = await readFile(path);
    if (digest(bytes) !== record.feedback_sha256) throw Error('Feedback content hash changed');
    const feedback = JSON.parse(bytes.toString('utf8'));
    if (!grade || feedback.grade_hash !== digest(grade) || feedback.rubric_hash !== record.rubric_hash) throw Error('Feedback source binding differs');
    return feedback;
  }
  async seal(rows, rubricHash) {
    if (this.sealed) return this.sealed;
    if (rows.length !== this.ids.length || new Set(rows.map(row => row.student_id)).size !== this.ids.length) throw Error('Incomplete result roster');
    const records = [];
    for (const id of this.ids) {
      const row = rows.find(row => row.student_id === id); const record = this.records.get(id);
      if (!row || !record || record.status !== row.status || record.rubric_hash !== rubricHash) throw Error('Wait for every result writer to finish');
      if (record.status === 'submitted') {
        const grade = await this.loadGrade(record); await this.loadFeedback(record, grade);
      }
      records.push(record);
    }
    const value = { version: 1, rubric_hash: rubricHash, records, result_set_hash: digest(records) };
    await freezeJson(this.directory, 'index.json', value); this.sealed = value; return value;
  }
  async read(ids) {
    if (!this.sealed) throw Error('Results are not sealed');
    if (!ids.length || new Set(ids).size !== ids.length || ids.some(id => !this.ids.includes(id))) throw Error('Invalid result selection');
    return Promise.all(ids.map(async id => {
      const stored = this.sealed.records.find(row => row.student_id === id);
      const bytes = await readFile(resolve(this.directory, `${id}.json`));
      if (digest(JSON.parse(bytes.toString('utf8'))) !== digest(stored)) throw Error('Result receipt changed');
      const grade = stored.status === 'submitted' ? await this.loadGrade(stored) : null;
      return { ...stored, grade, feedback: await this.loadFeedback(stored, grade) };
    }));
  }
}
