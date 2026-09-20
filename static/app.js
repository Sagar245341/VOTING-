const pollList = document.querySelector("#poll-list");
const createForm = document.querySelector("#create-form");
const toast = document.querySelector("#toast");

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

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.className = `toast visible${isError ? " error" : ""}`;
  window.setTimeout(() => toast.classList.remove("visible"), 3200);
}

function renderPoll(poll) {
  const options = poll.options
    .map(
      (option) => `
    <label class="option-row">
      <input type="radio" name="poll-${poll.id}" value="${option.id}" />
      <span class="radio"></span>
      <span class="option-name">${escapeHtml(option.label)}</span>
      <span class="result-count">${option.votes} <small>${option.votes === 1 ? "vote" : "votes"}</small></span>
      <span class="bar"><span style="width: ${option.percentage}%"></span></span>
    </label>`,
    )
    .join("");

  return `<article class="poll-card" data-poll-id="${poll.id}">
    <div class="poll-heading">
      <div><span class="poll-number">0${poll.id}</span><h2>${escapeHtml(poll.question)}</h2></div>
      <span class="vote-total">${poll.total_votes} total</span>
    </div>
    <p class="poll-description">${escapeHtml(poll.description)}</p>
    <form class="vote-form" data-poll-id="${poll.id}">
      <div class="options">${options}</div>
      <div class="vote-actions"><input name="voter_name" required minlength="2" maxlength="80" placeholder="Your name" /><button type="submit">Submit vote <span>→</span></button></div>
    </form>
  </article>`;
}

async function loadPolls() {
  try {
    const response = await fetch("/api/polls");
    if (!response.ok) throw new Error("Could not load polls");
    const polls = await response.json();
    pollList.innerHTML = polls.length
      ? polls.map(renderPoll).join("")
      : '<div class="empty">No polls yet. Start the first one below.</div>';
  } catch (error) {
    pollList.innerHTML =
      '<div class="empty error-text">The voting room is unavailable right now.</div>';
  }
}

pollList.addEventListener("submit", async (event) => {
  if (!event.target.matches(".vote-form")) return;
  event.preventDefault();
  const form = event.target;
  const option = form.querySelector('input[type="radio"]:checked');
  if (!option) return showToast("Choose an option first.", true);

  const response = await fetch(`/api/polls/${form.dataset.pollId}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      voter_name: form.voter_name.value,
      option_id: Number(option.value),
    }),
  });
  const result = await response.json();
  if (!response.ok)
    return showToast(result.detail || "Vote could not be recorded.", true);
  showToast("Your vote is in.");
  await loadPolls();
});

createForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(createForm);
  const options = formData
    .getAll("option")
    .map((option) => option.trim())
    .filter(Boolean);
  const response = await fetch("/api/polls", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: formData.get("question"),
      description: formData.get("description"),
      options,
    }),
  });
  const result = await response.json();
  if (!response.ok)
    return showToast(result.detail || "Poll could not be created.", true);
  createForm.reset();
  showToast("New poll created.");
  await loadPolls();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

loadPolls();
