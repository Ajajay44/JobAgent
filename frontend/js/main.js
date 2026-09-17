/**
 * JobUndo — Frontend JavaScript
 *
 * Responsibilities (Phase 1 skeleton):
 * - Resume file upload (drag & drop + click)
 * - Form validation & Generate button state
 * - Progress stepper UI (ready for SSE in Phase 10)
 * - Character counter for JD textarea
 * - Header scroll effect
 *
 * Phase 10 will wire this to the actual SSE stream.
 */

'use strict';

// ── Constants ─────────────────────────────────────────────────────────────────
const MAX_FILE_SIZE_MB = 10;
const MAX_JD_CHARS = 20_000;
const MIN_JD_CHARS = 50;

const API_BASE = '/api';

// ── State ─────────────────────────────────────────────────────────────────────
let resumeFile = null;
let isProcessing = false;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const dropZone        = document.getElementById('drop-zone');
const fileInput       = document.getElementById('resume-file-input');
const filePreview     = document.getElementById('file-preview');
const fileName        = document.getElementById('file-name');
const fileSize        = document.getElementById('file-size');
const btnRemoveFile   = document.getElementById('btn-remove-file');
const jdInput         = document.getElementById('jd-input');
const charCount       = document.getElementById('char-count');
const btnGenerate     = document.getElementById('btn-generate');
const btnNewApp       = document.getElementById('btn-new-application');
const progressCard    = document.getElementById('progress-card');
const progressStatus  = document.getElementById('progress-status');
const resultsCard     = document.getElementById('results-card');
const header          = document.getElementById('header');

// ── Step element map ──────────────────────────────────────────────────────────
const STEP_MAP = {
  parse_jd:              document.getElementById('step-parse-jd'),
  parse_resume:          document.getElementById('step-parse-resume'),
  skill_gap_analysis:    document.getElementById('step-skill-gap'),
  company_research:      document.getElementById('step-company'),
  resume_rewriter:       document.getElementById('step-resume-rewriter'),
  cover_letter_generator:document.getElementById('step-cover-letter'),
  cold_email_drafter:    document.getElementById('step-emails'),
  quality_checker:       document.getElementById('step-quality'),
};

// ── Header scroll effect ──────────────────────────────────────────────────────
window.addEventListener('scroll', () => {
  header.classList.toggle('header--scrolled', window.scrollY > 20);
}, { passive: true });

// ── File upload ───────────────────────────────────────────────────────────────

/** Validate and accept a File object */
function handleFile(file) {
  if (!file) return;

  // Type check
  if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
    showError('Only PDF files are accepted.');
    return;
  }

  // Size check
  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    showError(`File too large. Maximum size is ${MAX_FILE_SIZE_MB} MB.`);
    return;
  }

  resumeFile = file;
  showFilePreview(file);
  updateGenerateButton();
}

function showFilePreview(file) {
  filePreview.hidden = false;
  fileName.textContent = file.name;
  fileSize.textContent = formatFileSize(file.size);
  dropZone.classList.add('drop-zone--has-file');
  dropZone.setAttribute('aria-label', `Resume uploaded: ${file.name}. Click to change.`);
}

function clearFile() {
  resumeFile = null;
  fileInput.value = '';
  filePreview.hidden = true;
  dropZone.classList.remove('drop-zone--has-file');
  dropZone.setAttribute('aria-label', 'Upload resume PDF — click or drag and drop');
  updateGenerateButton();
}

// Click to open file picker
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
});

fileInput.addEventListener('change', () => {
  if (fileInput.files?.[0]) handleFile(fileInput.files[0]);
});

// Drag & drop
dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drop-zone--dragover');
});
dropZone.addEventListener('dragleave', e => {
  if (!dropZone.contains(e.relatedTarget)) {
    dropZone.classList.remove('drop-zone--dragover');
  }
});
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drop-zone--dragover');
  const file = e.dataTransfer?.files?.[0];
  if (file) handleFile(file);
});

btnRemoveFile.addEventListener('click', e => {
  e.stopPropagation();
  clearFile();
});

// ── JD textarea ───────────────────────────────────────────────────────────────
jdInput.addEventListener('input', () => {
  const len = jdInput.value.length;
  charCount.textContent = len.toLocaleString();

  // Color hint
  if (len > MAX_JD_CHARS * 0.9) {
    charCount.style.color = 'var(--warning)';
  } else if (len >= MIN_JD_CHARS) {
    charCount.style.color = 'var(--success)';
  } else {
    charCount.style.color = '';
  }

  updateGenerateButton();
});

// ── Generate button validation ────────────────────────────────────────────────
function updateGenerateButton() {
  const jdLen = jdInput.value.trim().length;
  const isValid = resumeFile && jdLen >= MIN_JD_CHARS && !isProcessing;
  btnGenerate.disabled = !isValid;
}

// ── Generate handler ──────────────────────────────────────────────────────────
btnGenerate.addEventListener('click', async () => {
  if (isProcessing || btnGenerate.disabled) return;
  startProcessing();
});

async function startProcessing() {
  isProcessing = true;
  setGenerateButtonLoading(true);
  resetSteps();
  updateProgressStatus('Starting…');

  /**
   * Phase 1: Simulate the agent pipeline with realistic timing.
   * Phase 3+: Replace this with a real SSE connection to FastAPI.
   *
   * SSE will look like:
   *   const evtSource = new EventSource(`/agent/api/agent/run/${runId}/stream`);
   *   evtSource.onmessage = (e) => handleSSEEvent(JSON.parse(e.data));
   */
  const steps = Object.keys(STEP_MAP);
  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    setStepActive(step);
    updateProgressStatus(`${stepLabel(step)}…`);
    await sleep(800 + Math.random() * 600);  // simulate variable node duration
    setStepDone(step);
  }

  finishProcessing();
}

function finishProcessing() {
  isProcessing = false;
  setGenerateButtonLoading(false);
  updateProgressStatus('Complete ✓');
  resultsCard.hidden = false;
  resultsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

btnNewApp.addEventListener('click', () => {
  resetAll();
});

// ── Step UI helpers ───────────────────────────────────────────────────────────

function setStepState(stepKey, state) {
  const el = STEP_MAP[stepKey];
  if (!el) return;
  el.className = `step-item step-item--${state}`;
}

function setStepActive(stepKey) { setStepState(stepKey, 'active'); }
function setStepDone(stepKey)   {
  setStepState(stepKey, 'done');
  const meta = STEP_MAP[stepKey]?.querySelector('.step-item__meta');
  if (meta) meta.textContent = 'done';
}
function setStepError(stepKey, msg) {
  setStepState(stepKey, 'error');
  const meta = STEP_MAP[stepKey]?.querySelector('.step-item__meta');
  if (meta) meta.textContent = msg || 'failed';
}

function resetSteps() {
  Object.keys(STEP_MAP).forEach(k => {
    setStepState(k, 'waiting');
    const meta = STEP_MAP[k]?.querySelector('.step-item__meta');
    if (meta) meta.textContent = '';
  });
}

function stepLabel(stepKey) {
  const labels = {
    parse_jd: 'Reading job description',
    parse_resume: 'Analysing resume',
    skill_gap_analysis: 'Matching experience',
    company_research: 'Researching company',
    resume_rewriter: 'Tailoring resume',
    cover_letter_generator: 'Writing cover letter',
    cold_email_drafter: 'Drafting emails',
    quality_checker: 'Checking quality',
  };
  return labels[stepKey] || stepKey;
}

// ── SSE handler (wired in Phase 10) ──────────────────────────────────────────
/**
 * handleSSEEvent(event)
 *
 * Called for each SSE message from FastAPI.
 * Example event format:
 *   { node: "parse_jd", status: "started", message: "...", duration_ms: 0 }
 *   { node: "parse_jd", status: "completed", duration_ms: 1240 }
 *
 * @param {Object} event
 */
function handleSSEEvent(event) {
  const { node, status, message, duration_ms } = event;
  updateProgressStatus(message || `${stepLabel(node)}…`);

  if (status === 'started') {
    setStepActive(node);
  } else if (status === 'completed') {
    const meta = STEP_MAP[node]?.querySelector('.step-item__meta');
    if (meta && duration_ms) meta.textContent = `${duration_ms}ms`;
    setStepDone(node);
  } else if (status === 'error') {
    setStepError(node, message);
  } else if (status === 'done') {
    finishProcessing();
  }
}

// ── UI state helpers ──────────────────────────────────────────────────────────
function setGenerateButtonLoading(loading) {
  const text = btnGenerate.querySelector('.btn__text');
  const spinner = btnGenerate.querySelector('.btn__spinner');
  text.textContent = loading ? 'Generating…' : 'Generate Application';
  spinner.hidden = !loading;
  btnGenerate.disabled = loading;
}

function updateProgressStatus(msg) {
  progressStatus.textContent = msg;
}

function resetAll() {
  clearFile();
  jdInput.value = '';
  charCount.textContent = '0';
  charCount.style.color = '';
  resultsCard.hidden = true;
  resetSteps();
  updateProgressStatus('Waiting…');
  setGenerateButtonLoading(false);
  isProcessing = false;
  updateGenerateButton();
}

function showError(msg) {
  // Phase 10: replace with proper toast/notification component
  alert(msg);
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Auth modal stubs (Phase 1 — wired to Django in Phase 2+) ─────────────────
document.getElementById('btn-login')?.addEventListener('click', () => {
  // Phase 2: open login modal or redirect to /login/
  console.log('[JobUndo] Login flow — Phase 2');
});
document.getElementById('btn-signup')?.addEventListener('click', () => {
  // Phase 2: open register modal or redirect to /register/
  console.log('[JobUndo] Register flow — Phase 2');
});

// ── Init ──────────────────────────────────────────────────────────────────────
updateGenerateButton();
console.log('[JobUndo] Frontend initialised — Phase 1');
