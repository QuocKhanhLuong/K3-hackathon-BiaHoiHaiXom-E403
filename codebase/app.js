const slides = [
  {
    page: 1,
    meta: "AI IN ACTION · Day 1",
    title: "AI & LLM Foundation",
    subtitle: "Nền tảng trí tuệ nhân tạo và mô hình ngôn ngữ lớn",
    description:
      "Hiểu các khái niệm cốt lõi của AI, cách LLM hoạt động và vai trò của chúng trong đời sống và công việc.",
    author: "Giảng viên: Mai Anh Nguyen (Blue)",
  },
  {
    page: 2,
    meta: "AI IN ACTION · Day 1",
    title: "Ứng dụng tiêu biểu của NLP",
    subtitle: "Từ hiểu ngôn ngữ đến hỗ trợ ra quyết định",
    description:
      "NLP giúp hệ thống dịch, hỏi đáp, tóm tắt, trích xuất thông tin và phân tích cảm xúc từ văn bản tự nhiên.",
    author: "Slide 2 · Khối kiến thức NLP",
  },
  {
    page: 3,
    meta: "NLP FOUNDATION",
    title: "Syntax và Semantics",
    subtitle: "Máy cần hiểu cả cấu trúc lẫn ý nghĩa",
    description:
      "Syntax kiểm tra câu được tạo thành như thế nào; semantics giúp mô hình hiểu điều người học thật sự muốn hỏi.",
    author: "Slide 3 · Nền tảng xử lý ngôn ngữ",
  },
  {
    page: 4,
    meta: "NLP IN ACTION",
    title: "Machine Translation",
    subtitle: "Dịch máy không chỉ là đổi từng từ",
    description:
      "Một hệ dịch tốt cần nhận diện ngữ cảnh, sắc thái, thuật ngữ miền và mục tiêu giao tiếp của người dùng.",
    author: "Slide 4 · Ví dụ thực tế",
  },
  {
    page: 5,
    meta: "LEARNING CHECK",
    title: "Từ câu trả lời đến câu hỏi tiếp",
    subtitle: "Tutor tốt cần chủ động kéo người học tiến thêm một bước",
    description:
      "Sau mỗi câu trả lời, hệ thống nên đưa ra follow-up phù hợp: hỏi sâu hơn, đưa ví dụ, quiz ngắn hoặc nhảy về slide liên quan.",
    author: "Slide 5 · Workflow học tập",
  },
];

const state = {
  currentSlide: 1,
  usage: 7,
  zoom: 100,
};

const selectors = {
  slideCard: document.querySelector("#slideCard"),
  slideMeta: document.querySelector("#slideMeta"),
  slideTitle: document.querySelector("#slideTitle"),
  slideSubtitle: document.querySelector("#slideSubtitle"),
  slideDescription: document.querySelector("#slideDescription"),
  slideAuthor: document.querySelector("#slideAuthor"),
  currentPageTop: document.querySelector("#currentPageTop"),
  pagePills: document.querySelector("#pagePills"),
  messages: document.querySelector("#messages"),
  composer: document.querySelector("#composer"),
  questionInput: document.querySelector("#questionInput"),
  usageCount: document.querySelector("#usageCount"),
  usageBar: document.querySelector("#usageBar"),
  zoomLabel: document.querySelector("#zoomLabel"),
  adapterRoute: document.querySelector("#adapterRoute"),
  adapterFlow: document.querySelector("#adapterFlow"),
};

function slideByPage(page) {
  return slides.find((slide) => slide.page === page) || slides[0];
}

function setSlide(page, animate = false) {
  const clamped = Math.max(1, Math.min(page, slides.length));
  const slide = slideByPage(clamped);
  state.currentSlide = clamped;

  selectors.slideMeta.textContent = slide.meta;
  selectors.slideTitle.textContent = slide.title;
  selectors.slideSubtitle.textContent = slide.subtitle;
  selectors.slideDescription.textContent = slide.description;
  selectors.slideAuthor.textContent = slide.author;
  selectors.currentPageTop.textContent = slide.page;

  renderPagePills();

  if (animate) {
    selectors.slideCard.classList.remove("cited");
    requestAnimationFrame(() => selectors.slideCard.classList.add("cited"));
    selectors.slideCard.focus();
  }
}

function renderPagePills() {
  selectors.pagePills.innerHTML = "";
  [1, 2, 3, "…", 83].forEach((page) => {
    if (page === "…") {
      const span = document.createElement("span");
      span.textContent = page;
      selectors.pagePills.appendChild(span);
      return;
    }

    const button = document.createElement("button");
    button.className = `page-pill${state.currentSlide === page ? " active" : ""}`;
    button.type = "button";
    button.textContent = page;
    button.addEventListener("click", () => setSlide(page, true));
    selectors.pagePills.appendChild(button);
  });
}

function addMessage(role, html) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = html;
  wrapper.appendChild(bubble);
  selectors.messages.appendChild(wrapper);
  selectors.messages.scrollTop = selectors.messages.scrollHeight;
  return wrapper;
}

function renderAdapterFlow(turn) {
  if (!selectors.adapterRoute || !selectors.adapterFlow) return;
  selectors.adapterRoute.textContent = turn.route;
  selectors.adapterFlow.innerHTML = "";

  turn.steps.forEach((step, index) => {
    const chip = document.createElement("span");
    chip.className = `flow-chip${index === turn.steps.length - 1 ? " active" : ""}`;
    chip.textContent = VLearnMockAdapter.flowLabels[step] || step;
    selectors.adapterFlow.appendChild(chip);
  });
}

function appendFollowUps(messageWrapper, followUps) {
  if (!followUps.length) {
    return;
  }

  const isQuiz = followUps.every((item) => item.type === "quiz-option");
  const followBlock = document.createElement("div");
  followBlock.className = "turn-followups";
  followBlock.innerHTML = `<div class="follow-title">${isQuiz ? "Chọn đáp án" : "Gợi ý tiếp theo"}</div>`;

  const followGrid = document.createElement("div");
  followGrid.className = `follow-grid${isQuiz ? " quiz-grid" : ""}`;

  followUps.forEach((item) => {
    const button = document.createElement("button");
    button.className = `follow-up${item.type === "quiz-option" ? " quiz-option" : ""}`;
    button.type = "button";
    button.innerHTML = `<span>${item.icon}</span><strong>${item.label}</strong><span>${item.type === "quiz-option" ? "" : "›"}</span>`;
    button.addEventListener("click", () => {
      if (item.type === "quiz-option") {
        handleQuizOption(followBlock, followGrid, button, item);
        return;
      }
      if (item.type === "goto") {
        setSlide(item.page, true);
        return;
      }
      submitQuestion(item.label);
    });
    followGrid.appendChild(button);
  });

  followBlock.appendChild(followGrid);
  messageWrapper.appendChild(followBlock);
  selectors.messages.scrollTop = selectors.messages.scrollHeight;
}

function handleQuizOption(followBlock, followGrid, selectedButton, item) {
  followGrid.querySelectorAll(".quiz-option").forEach((button) => {
    button.disabled = true;
    button.classList.add("disabled");
  });

  selectedButton.classList.add(item.correct ? "correct" : "wrong");
  selectedButton.querySelector("span:last-child").textContent = item.correct ? "✓" : "✕";

  const feedback = document.createElement("div");
  feedback.className = `quiz-feedback ${item.correct ? "correct" : "wrong"}`;
  feedback.textContent = item.correct ? "Đúng rồi." : item.feedback;
  followBlock.appendChild(feedback);
  VLearnMockAdapter.resolveInlineCheck();
  selectors.messages.scrollTop = selectors.messages.scrollHeight;
}

function appendWaitingState(messageWrapper) {
  const followBlock = document.createElement("div");
  followBlock.className = "turn-followups";
  followBlock.innerHTML = `
    <div class="follow-title">Gợi ý tiếp theo</div>
    <div class="follow-empty waiting">Đang chờ học viên nhập câu trả lời làm rõ trong ô chat.</div>
  `;
  messageWrapper.appendChild(followBlock);
  selectors.messages.scrollTop = selectors.messages.scrollHeight;
}

function setComposerMode(turn = {}) {
  selectors.questionInput.placeholder =
    turn.inputPlaceholder || "Nhập câu hỏi hoặc yêu cầu của bạn...";
  selectors.composer.classList.toggle("awaiting-input", Boolean(turn.awaitingInput));
}

function updateUsage() {
  state.usage = Math.min(15, state.usage + 1);
  if (selectors.usageCount) selectors.usageCount.textContent = state.usage;
  if (selectors.usageBar) selectors.usageBar.style.width = `${(state.usage / 15) * 100}%`;
}

function renderTutorTurn(turn) {
  renderAdapterFlow(turn);
  const botMessage = addMessage("bot", turn.answer);
  setComposerMode(turn);
  if (turn.awaitingInput) {
    appendWaitingState(botMessage);
    selectors.questionInput.focus();
    return;
  }
  appendFollowUps(botMessage, turn.followUps);
}

function submitQuestion(question) {
  const trimmed = question.trim();
  if (!trimmed) return;

  addMessage("user", trimmed);
  selectors.questionInput.value = "";
  selectors.questionInput.style.height = "auto";
  setComposerMode();
  updateUsage();

  const turn = VLearnMockAdapter.makeTurn(trimmed, {
    currentSlide: state.currentSlide,
  });

  setTimeout(() => {
    renderTutorTurn(turn);
  }, 260);
}

function resetChat() {
  state.usage = 7;
  selectors.messages.innerHTML = "";
  if (selectors.usageCount) selectors.usageCount.textContent = state.usage;
  if (selectors.usageBar) selectors.usageBar.style.width = `${(state.usage / 15) * 100}%`;
  setSlide(1);
  renderTutorTurn(VLearnMockAdapter.getInitialTurn());
}

document.querySelector("#prevSlide").addEventListener("click", () => setSlide(state.currentSlide - 1, true));
document.querySelector("#nextSlide").addEventListener("click", () => setSlide(state.currentSlide + 1, true));
document.querySelector("#pagerPrev").addEventListener("click", () => setSlide(state.currentSlide - 1, true));
document.querySelector("#pagerNext").addEventListener("click", () => setSlide(state.currentSlide + 1, true));
document.querySelector("#resetChat").addEventListener("click", resetChat);

document.querySelector("#zoomOut").addEventListener("click", () => {
  state.zoom = Math.max(80, state.zoom - 10);
  selectors.zoomLabel.textContent = `${state.zoom}%`;
});

document.querySelector("#zoomIn").addEventListener("click", () => {
  state.zoom = Math.min(140, state.zoom + 10);
  selectors.zoomLabel.textContent = `${state.zoom}%`;
});

selectors.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  submitQuestion(selectors.questionInput.value);
});

selectors.questionInput.addEventListener("input", () => {
  selectors.questionInput.style.height = "auto";
  selectors.questionInput.style.height = `${selectors.questionInput.scrollHeight}px`;
});

selectors.questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    selectors.composer.requestSubmit();
  }
});

selectors.messages.addEventListener("click", (event) => {
  const citation = event.target.closest(".citation");
  if (!citation) return;
  event.preventDefault();
  setSlide(Number(citation.dataset.page), true);
});

setSlide(1);
resetChat();
