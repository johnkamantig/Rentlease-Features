import {segments} from './highlight.js';

const $ = id => document.getElementById(id);
let cloudData = null;
let selected = null;
let generation = 0;
let retryAction = loadCloud;

async function get(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

function message(text) { $('status').textContent = text; }
function busy(value) { $('reviews').setAttribute('aria-busy', String(value)); }
function fail(text, action) {
  message(text);
  retryAction = action;
  $('retry').hidden = false;
  busy(false);
}

function renderReviews(reviews) {
  $('reviews').replaceChildren();
  for (const review of reviews) {
    const article = document.createElement('article');
    article.className = 'review';
    const title = document.createElement('h3');
    title.textContent = `Synthetic review · ${review.id}`;
    const body = document.createElement('p');
    for (const part of segments(review.text, review.spans)) {
      const node = document.createElement(part.marked ? 'mark' : 'span');
      node.textContent = part.text; // Never interpret review text as HTML.
      body.append(node);
    }
    article.append(title, body);
    $('reviews').append(article);
  }
  busy(false);
}

function selectionState(id) {
  selected = id;
  for (const button of $('cloud').querySelectorAll('button')) {
    button.setAttribute('aria-pressed', String(button.dataset.id === id));
  }
  $('reset').hidden = !id;
}

function reset() {
  generation++;
  selectionState(null);
  $('retry').hidden = true;
  $('reviews-title').textContent = 'Original reviews';
  renderReviews(cloudData?.reviews || []);
  message(cloudData ? `${cloudData.eligible_review_count} eligible synthetic reviews. Select a term to filter.` : 'Choose a sample property.');
}

async function selectTerm(term) {
  const ticket = ++generation;
  selectionState(term.id);
  $('retry').hidden = true;
  $('reviews-title').textContent = `Reviews mentioning “${term.text}”`;
  $('reviews').replaceChildren();
  busy(true);
  message('Loading matching original reviews…');
  const property = $('property').value;
  try {
    const data = await get(`/properties/${encodeURIComponent(property)}/wordcloud/terms/${encodeURIComponent(term.id)}/reviews`);
    if (ticket !== generation) return;
    renderReviews(data.reviews);
    message(`Mentioned in ${data.term.review_count} distinct eligible reviews.`);
  } catch {
    if (ticket === generation) fail('Could not load matching reviews. Try again.', () => selectTerm(term));
  }
}

async function loadCloud() {
  const ticket = ++generation;
  cloudData = null;
  selectionState(null);
  $('retry').hidden = true;
  $('cloud').replaceChildren();
  $('reviews').replaceChildren();
  $('total').textContent = '';
  $('reviews-title').textContent = 'Original reviews';
  $('cloud').setAttribute('aria-busy', 'true');
  const loading = document.createElement('p');
  loading.className = 'state';
  loading.textContent = 'Loading frequently mentioned terms…';
  $('cloud').append(loading);
  busy(true);
  message('Loading synthetic reviews…');
  try {
    const data = await get(`/properties/${encodeURIComponent($('property').value)}/wordcloud`);
    if (ticket !== generation) return;
    cloudData = data;
    $('total').textContent = `${data.eligible_review_count} reviews`;
    $('cloud').replaceChildren();
    for (const term of data.terms) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'term';
      button.textContent = term.text;
      button.dataset.id = term.id;
      button.dataset.color = term.color;
      button.style.setProperty('--size', `${term.font_size_rem}rem`);
      button.style.fontSize = `${term.font_size_rem}rem`;
      button.setAttribute('aria-label', `${term.text}, mentioned in ${term.review_count} distinct reviews`);
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => selectTerm(term));
      $('cloud').append(button);
    }
    if (data.status !== 'ready') {
      const empty = document.createElement('p');
      empty.className = 'state';
      empty.textContent = data.status === 'empty' ? 'No eligible published reviews yet.' :
        `Not enough recurring terms yet. At least ${data.thresholds.min_usable_reviews} usable reviews and ${data.thresholds.min_review_mentions} review mentions per term are needed.`;
      $('cloud').append(empty);
    }
    $('cloud').setAttribute('aria-busy', 'false');
    reset();
  } catch {
    if (ticket !== generation) return;
    $('cloud').replaceChildren();
    $('cloud').textContent = 'Word cloud unavailable.';
    $('cloud').setAttribute('aria-busy', 'false');
    fail('Could not load this property. Check the local server and retry.', loadCloud);
  }
}

$('reset').addEventListener('click', reset);
$('retry').addEventListener('click', () => retryAction());
$('property').addEventListener('change', loadCloud);
$('theme').addEventListener('click', () => {
  const dark = document.documentElement.dataset.theme !== 'dark';
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  $('theme').textContent = dark ? 'Light theme' : 'Dark theme';
  $('theme').setAttribute('aria-label', `Switch to ${dark ? 'light' : 'dark'} theme`);
});

async function initialize() {
  try {
    const properties = await get('/properties');
    $('property').replaceChildren();
    for (const property of properties) {
      const option = document.createElement('option');
      option.value = property.id;
      option.textContent = property.name;
      $('property').append(option);
    }
    $('property').disabled = false;
    await loadCloud();
  } catch {
    $('cloud').textContent = 'Sample properties unavailable.';
    $('cloud').setAttribute('aria-busy', 'false');
    fail('Could not load sample properties. Check the local server and retry.', initialize);
  }
}
initialize();
