const pdfInput = document.getElementById("pdfInput");
const fileNameDisplay = document.getElementById("fileNameDisplay");
const uploadBtn = document.getElementById("uploadBtn");
const uploadStatus = document.getElementById("uploadStatus");
const chatCard = document.getElementById("chatCard");
const chatWindow = document.getElementById("chatWindow");
const questionInput = document.getElementById("questionInput");
const askBtn = document.getElementById("askBtn");

let selectedFile = null;

pdfInput.addEventListener("change", () => {
  if (pdfInput.files.length > 0) {
    selectedFile = pdfInput.files[0];
    fileNameDisplay.textContent = selectedFile.name;
    uploadBtn.disabled = false;
  }
});

uploadBtn.addEventListener("click", async () => {
  if (!selectedFile) return;

  uploadBtn.disabled = true;
  setStatus("Uploading and processing PDF... this can take a moment.", "");

  const formData = new FormData();
  formData.append("pdf_file", selectedFile);

  try {
    const res = await fetch("/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      setStatus(data.error || "Upload failed.", "error");
      uploadBtn.disabled = false;
      return;
    }

    setStatus(`${data.message} (${data.num_chunks} chunks indexed)`, "success");
    chatCard.style.display = "block";
    questionInput.disabled = false;
    askBtn.disabled = false;
    addBubble("bot", `I've read "${selectedFile.name}". Ask me anything about it.`);
  } catch (err) {
    setStatus("Network error while uploading.", "error");
    uploadBtn.disabled = false;
  }
});

askBtn.addEventListener("click", sendQuestion);
questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendQuestion();
});

async function sendQuestion() {
  const question = questionInput.value.trim();
  if (!question) return;

  addBubble("user", question);
  questionInput.value = "";
  askBtn.disabled = true;

  const loadingBubble = addBubble("bot", "Thinking...", true);

  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();

    loadingBubble.remove();

    if (!res.ok) {
      addBubble("bot", data.error || "Something went wrong.");
    } else {
      addBubble("bot", data.answer);
    }
  } catch (err) {
    loadingBubble.remove();
    addBubble("bot", "Network error while asking.");
  } finally {
    askBtn.disabled = false;
  }
}

function addBubble(role, text, loading = false) {
  const div = document.createElement("div");
  div.className = `bubble ${role}${loading ? " loading" : ""}`;
  div.textContent = text;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return div;
}

function setStatus(msg, type) {
  uploadStatus.textContent = msg;
  uploadStatus.className = `status ${type}`;
}
