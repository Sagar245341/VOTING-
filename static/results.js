const resultsList = document.querySelector("#results-list");

const escapeHtml = (value) =>
  String(value).replace(
    /[&<>'"]/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#039;",
        '"': "&quot;",
      })[character],
  );

function renderResult(poll) {
  const leader = poll.options.reduce(
    (best, option) => (option.votes > best.votes ? option : best),
    poll.options[0],
  );
  const options = poll.options
    .map(
      (option) => `
    <div class="result-option${option.id === leader.id && option.votes > 0 ? " leader" : ""}">
      <div class="result-label"><span>${escapeHtml(option.label)}</span><strong>${option.percentage}%</strong></div>
      <div class="result-track"><span style="width: ${option.percentage}%"></span></div>
      <small>${option.votes} ${option.votes === 1 ? "vote" : "votes"}</small>
    </div>`,
    )
    .join("");

  return `<article class="result-card">
    <div class="result-card-head"><span class="poll-number">0${poll.id}</span><span class="vote-total">${poll.total_votes} total ${poll.total_votes === 1 ? "vote" : "votes"}</span></div>
    <h2>${escapeHtml(poll.question)}</h2>
    <p>${escapeHtml(poll.description)}</p>
    <div class="result-options">${options}</div>
    <div class="leading-choice">${poll.total_votes ? `Leading choice: <strong>${escapeHtml(leader.label)}</strong>` : "No votes yet"}</div>
  </article>`;
}

async function loadResults() {
  try {
    const response = await fetch("/api/results");
    if (!response.ok) throw new Error("Could not load results");
    const polls = await response.json();
    resultsList.innerHTML = polls.length
      ? polls.map(renderResult).join("")
      : '<div class="empty">No results are available yet.</div>';
  } catch (error) {
    resultsList.innerHTML =
      '<div class="empty error-text">Results are unavailable right now.</div>';
  }
}

loadResults();
