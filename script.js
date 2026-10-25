const form = document.querySelector("#chat-form");
const questionInput = document.querySelector("#question");
const messages = document.querySelector("#messages");
const sendButton = document.querySelector("#send-button");

function addMessage(text, role) {
  const message = document.createElement("div");
  message.className = `message ${role}`;
  message.innerHTML = `<span class="avatar">${role === "user" ? "YOU" : "AI"}</span><div class="bubble"></div>`;
  message.querySelector(".bubble").textContent = text;
  messages.appendChild(message);
  messages.scrollTop = messages.scrollHeight;
  return message.querySelector(".bubble");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question || sendButton.disabled) return;
  addMessage(question, "user");
  questionInput.value = "";
  sendButton.disabled = true;
  const answer = addMessage("", "assistant");
  try {
    const response = await fetch("/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question })
    });
    if (!response.ok || !response.body) throw new Error("Chat request failed");
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      const events = buffer.split("\n\n");
      buffer = events.pop();
      events.forEach((event) => {
        const token = event.replace(/^data:\s?/, "");
        if (token !== "[DONE]") answer.textContent += JSON.parse(token);
        messages.scrollTop = messages.scrollHeight;
      });
    }
  } catch (error) {
    answer.textContent = "Sorry, I could not reach the chatbot service.";
  } finally {
    sendButton.disabled = false;
    questionInput.focus();
  }
});
