/**
 * VLearn Adaptive Tutor Frontend Engine
 * Implements Updated Workflow Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // App State
  let currentPage = 1;
  let totalPages = 5;
  let slidesData = [];
  let selectedTextOnSlide = "";
  let chatHistory = [];
  let currentThreadId = null;

  // DOM Elements
  const leftPane = document.getElementById('leftPane');
  const rightPane = document.getElementById('rightPane');
  const resizer = document.getElementById('resizer');
  
  const slideTitle = document.getElementById('slideTitle');
  const slideSubtitle = document.getElementById('slideSubtitle');
  const slideBody = document.getElementById('slideBody');
  const slideFileRef = document.getElementById('slideFileRef');
  const currentPageNum = document.getElementById('currentPageNum');
  const totalPagesNum = document.getElementById('totalPagesNum');
  const tutorSlideBadge = document.getElementById('tutorSlideBadge');
  const selectionTooltip = document.getElementById('selectionTooltip');

  const notePageNum = document.getElementById('notePageNum');
  const pageNoteBadge = document.getElementById('pageNoteBadge');
  const noteTextarea = document.getElementById('noteTextarea');
  const noteSaveStatus = document.getElementById('noteSaveStatus');
  const notePanel = document.getElementById('notePanel');
  const toggleNoteBtn = document.getElementById('toggleNoteBtn');

  const prevPageBtn = document.getElementById('prevPageBtn');
  const nextPageBtn = document.getElementById('nextPageBtn');

  const chatMessages = document.getElementById('chatMessages');
  const chatInput = document.getElementById('chatInput');
  const sendBtn = document.getElementById('sendBtn');
  const activeNodeBadge = document.getElementById('activeNodeBadge');

  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const wfModal = document.getElementById('wfModal');
  const openWfModalBtn = document.getElementById('openWfModalBtn');
  const closeWfModalBtn = document.getElementById('closeWfModalBtn');

  // 1. Fetch & Render Slides
  async function loadSlides() {
    try {
      const res = await fetch('/api/slides');
      const data = await res.json();
      slidesData = data.slides;
      totalPages = data.total_pages;
      totalPagesNum.textContent = totalPages;
      renderSlide(currentPage);
    } catch (err) {
      console.warn('Backend not available, using fallback slides:', err);
      slidesData = [
        {
          page: 1,
          title: "AI Product Thinking & Requirements",
          subtitle: "AICB-P1 · Ngày 5 · Build agent xong, nhưng sản phẩm cho ai?",
          content: "<p><b>Tên Giảng Viên:</b> VinUniversity Phase 1 Tuần 1 2026.</p><p>Giới thiệu tổng quan về tư duy thiết kế sản phẩm AI cho người dùng thật. Không dừng lại ở prototype kỹ thuật mà tập trung vào giá trị mang lại cho end-user.</p>",
          code: "Lecture_material_ms204v3b_r9mo78"
        },
        {
          page: 2,
          title: "HÃY SUY NGHĨ: Bạn đã build xong Agent chưa?",
          subtitle: "Vấn đề của người dùng vs Prototype kỹ thuật",
          content: "<p>Nhiều đội nhóm tập trung 90% thời gian gọi API và chỉnh prompt, nhưng quên mất người dùng gặp vấn đề gì.</p><p>Bài toán sản phẩm AI đòi hỏi bằng chứng thực tế từ khảo sát hoặc data mining chứ không phải cảm tính.</p>",
          code: "Lecture_material_ms204v3b_r9mo78"
        },
        {
          page: 3,
          title: "Khung Xác định Bài toán & Chỗ khó (Taxonomy)",
          subtitle: "4 Lớp Chỗ Khó Cần Thiết Kế Cụ Thể",
          content: "<p>Duyệt qua 4 lớp chỗ khó theo Taxonomy:</p><ul><li><b>① Nguồn sự thật (Grounding):</b> Chỗ nào AI bịa được?</li><li><b>② Mơ mơ / Thiếu thông tin:</b> Input không đủ chắc thì hỏi lại hay đoán?</li><li><b>③ Ngoài thẩm quyền:</b> User đòi thứ không cho phép.</li><li><b>④ Đặc thù Domain:</b> Sai cái gì thì mất điểm/mất niềm tin?</li></ul>",
          code: "Lecture_material_ms204v3b_r9mo78"
        },
        {
          page: 4,
          title: "Function Calling & Agent Tools Contract",
          subtitle: "Cho Model Một \"Hợp Đồng\" Rõ Ràng",
          content: "<p>Text-based ReAct vs Structured Function Calling.</p><p>Function Calling cung cấp hợp đồng rõ ràng dạng <b>JSON Schema</b> giúp Agent thực thi hành động chính xác thay vì tự đoán văn bản ngẫu nhiên.</p>",
          code: "Lecture_material_ms204v3b_r9mo78"
        },
        {
          page: 5,
          title: "Quản lý Ngữ cảnh (Context Management)",
          subtitle: "Phân bổ Token Budget Cân Bằng",
          content: "<p>Context bao gồm 5 thành phần chính:</p><ul><li><b>System policy:</b> Định nghĩa vai trò & luật lệ.</li><li><b>History:</b> Lịch sử hội thoại gần đây.</li><li><b>Current input:</b> Yêu cầu của người dùng.</li><li><b>Tools schemas:</b> Định nghĩa công cụ.</li><li><b>Output buffer:</b> Khoảng trống sinh kết quả.</li></ul>",
          code: "Lecture_material_ms204v3b_r9mo78"
        }
      ];
      totalPages = slidesData.length;
      totalPagesNum.textContent = totalPages;
      renderSlide(currentPage);
    }
  }

  function renderSlide(pageNum) {
    const slide = slidesData.find(s => s.page === pageNum) || slidesData[0];
    slideTitle.textContent = slide.title;
    slideSubtitle.textContent = slide.subtitle || "";
    slideBody.innerHTML = slide.content;
    slideFileRef.textContent = slide.code || "day05-ai-product-thinking-requirements.pdf";

    currentPageNum.textContent = pageNum;
    tutorSlideBadge.textContent = pageNum;
    notePageNum.textContent = pageNum;
    pageNoteBadge.textContent = `Trang ${pageNum} · 1 note`;

    const savedNote = localStorage.getItem(`vlearn_note_page_${pageNum}`) || "";
    noteTextarea.value = savedNote;
  }

  // 2. Note Auto-Save
  noteTextarea.addEventListener('input', () => {
    noteSaveStatus.textContent = "Đang lưu...";
    localStorage.setItem(`vlearn_note_page_${currentPage}`, noteTextarea.value);
    setTimeout(() => {
      noteSaveStatus.textContent = "Đã lưu";
    }, 600);
  });

  toggleNoteBtn.addEventListener('click', () => {
    notePanel.style.display = notePanel.style.display === 'none' ? 'flex' : 'none';
  });

  // 3. Page Navigation
  prevPageBtn.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      renderSlide(currentPage);
    }
  });

  nextPageBtn.addEventListener('click', () => {
    if (currentPage < totalPages) {
      currentPage++;
      renderSlide(currentPage);
    }
  });

  // 4. Slide Text Selection Tooltip
  document.getElementById('slideCard').addEventListener('mouseup', (e) => {
    const sel = window.getSelection();
    const text = sel.toString().trim();
    if (text.length > 3) {
      selectedTextOnSlide = text;
      selectionTooltip.style.top = `${e.offsetY - 35}px`;
      selectionTooltip.style.left = `${e.offsetX + 10}px`;
      selectionTooltip.style.display = 'block';
    } else {
      selectionTooltip.style.display = 'none';
    }
  });

  selectionTooltip.addEventListener('click', () => {
    chatInput.value = `(Trang ${currentPage}, đoạn được chọn: "${selectedTextOnSlide}") Hãy giải thích đoạn này`;
    selectionTooltip.style.display = 'none';
    chatInput.focus();
  });

  // 5. Chat Messaging & Multi-Agent API Engine
  async function sendMessage(textOverride = null) {
    const text = textOverride || chatInput.value.trim();
    if (!text) return;

    appendMessage('student', text);
    if (!textOverride) chatInput.value = '';

    activeNodeBadge.textContent = "⚙️ Đang suy nghĩ...";
    activeNodeBadge.style.background = "#fef08a";

    try {
      const res = await fetch('/api/tutor/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: text,
          selected_text: selectedTextOnSlide,
          page_number: currentPage,
          chat_history: chatHistory
        })
      });

      const data = await res.json();
      
      // Save thread_id for subsequent interactions
      if (data.thread_id) {
          currentThreadId = data.thread_id;
      }
      
      activeNodeBadge.textContent = `📍 ${data.orchestrator.title}`;
      activeNodeBadge.style.background = "#dcfce7";

      // Render Grounded Answer (contains Deep-dive Expansion if branch == 'followup')
      appendTutorAnswer(data.answer, data.citations, data.orchestrator);

      // Render Tool Card based on Orchestrator decision
      if (data.tool_data) {
        if (data.orchestrator.branch === 'clarify') {
          renderClarificationCard(data.tool_data);
        } else if (data.orchestrator.branch === 'understanding_check' || data.orchestrator.branch === 'followup') {
          // If branch is 'followup', after Mở rộng tri thức -> points to Understanding Check (Quiz)!
          renderQuizCard(data.tool_data);
        }
      }

      // Render 3 Default Follow-up Suggestions Chips in ALL cases before ending turn
      if (data.default_suggestions) {
        renderFollowupChips(data.default_suggestions);
      }

      selectedTextOnSlide = "";
    } catch (err) {
      console.error('API Error:', err);
      activeNodeBadge.textContent = "📍 Cần kiểm tra hiểu";
      appendTutorAnswer(`Dựa trên slide trang ${currentPage}, mình đã cập nhật câu trả lời có căn cứ cho bạn [trang ${currentPage}].`, [currentPage], { title: "Cần kiểm tra hiểu" });
      renderQuizCard({
        quiz_id: "q_demo",
        quiz_type: "short_answer",
        concept: "Vận dụng Cốt lõi",
        question: "Theo bạn, tại sao Function Calling lại được gọi là 'Hợp đồng' giữa Agent và hệ thống? (Gõ 1-2 câu trả lời vào ô dưới):",
        expected_keywords: ["schema", "hợp đồng", "cấu trúc", "json"]
      });
      renderFollowupChips([
        "Làm sao áp dụng khái niệm này vào bài thi Hackathon nhóm mình?",
        "Các lỗi phổ biến học viên hay gặp khi triển khai phần này là gì?",
        "Ví dụ 1 kịch bản fail tiêu biểu và cách khắc phục?"
      ]);
    }
  }

  function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `msg-bubble msg-${role}`;
    msgDiv.textContent = text;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendTutorAnswer(text, citations = [], orchestrator = {}) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'msg-bubble msg-tutor';

    let citationHTML = "";
    if (citations && citations.length > 0) {
      citationHTML = citations.map(c => `<span class="citation-tag">[trang ${c}]</span>`).join('');
    }

    msgDiv.innerHTML = `
      <div style="font-size:11px; color:#64748b; margin-bottom:4px;">
        <i class="fa-solid fa-diagram-project"></i> ${orchestrator.title || "Tutor trả lời"}
      </div>
      <div>${text} ${citationHTML}</div>
    `;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // Tool Render 1: Clarification Options
  function renderClarificationCard(clarifyData) {
    const card = document.createElement('div');
    card.className = 'quiz-card';
    card.innerHTML = `
      <div class="quiz-header"><i class="fa-solid fa-circle-question"></i> Hỏi làm rõ</div>
      <div class="quiz-question">${clarifyData.clarifying_question}</div>
      <div class="quiz-options">
        ${clarifyData.suggested_inputs.map(opt => `<button class="quiz-opt-btn clarify-opt-btn">${opt}</button>`).join('')}
      </div>
    `;
    chatMessages.appendChild(card);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    card.querySelectorAll('.clarify-opt-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        sendMessage(btn.textContent);
      });
    });
  }

  // Tool Render 2: Interactive Quiz Card
  function renderQuizCard(quizData) {
    const card = document.createElement('div');
    card.className = 'quiz-card';

    const isShortAnswer = (quizData.quiz_type === 'short_answer' || !quizData.options || quizData.options.length === 0);

    if (isShortAnswer) {
      card.innerHTML = `
        <div class="quiz-header"><i class="fa-solid fa-pen-to-square"></i> Understanding Check (Tự luận ngắn) — ${quizData.concept}</div>
        <div class="quiz-question">${quizData.question}</div>
        <div class="short-answer-wrapper">
          <input type="text" class="short-answer-input" placeholder="Gõ câu trả lời của bạn tại đây...">
          <button class="short-answer-submit-btn"><i class="fa-solid fa-paper-plane"></i> Gửi câu trả lời</button>
        </div>
      `;
      chatMessages.appendChild(card);
      chatMessages.scrollTop = chatMessages.scrollHeight;

      const shortInput = card.querySelector('.short-answer-input');
      const submitBtn = card.querySelector('.short-answer-submit-btn');

      const handleShortSubmit = async () => {
        const userText = shortInput.value.trim();
        if (!userText) return;
        shortInput.disabled = true;
        submitBtn.disabled = true;

        await submitQuizPayload({
          quiz_id: quizData.quiz_id,
          thread_id: currentThreadId,
          quiz_type: "short_answer",
          user_text_answer: userText,
          expected_keywords: quizData.expected_keywords || [],
          question_text: quizData.question,
          page_number: currentPage
        }, card);
      };

      submitBtn.addEventListener('click', handleShortSubmit);
      shortInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleShortSubmit();
      });

    } else {
      card.innerHTML = `
        <div class="quiz-header"><i class="fa-solid fa-square-check"></i> Understanding Check (Trắc nghiệm) — ${quizData.concept}</div>
        <div class="quiz-question">${quizData.question}</div>
        <div class="quiz-options">
          ${quizData.options.map((opt, idx) => `<button class="quiz-opt-btn quiz-choice-btn" data-idx="${idx}">${opt}</button>`).join('')}
        </div>
      `;
      chatMessages.appendChild(card);
      chatMessages.scrollTop = chatMessages.scrollHeight;

      card.querySelectorAll('.quiz-choice-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          const selectedIdx = parseInt(btn.getAttribute('data-idx'));
          await submitQuizPayload({
            quiz_id: quizData.quiz_id,
            thread_id: currentThreadId,
            quiz_type: "multiple_choice",
            selected_option: selectedIdx,
            correct_option: quizData.correct_index,
            question_text: quizData.question,
            page_number: currentPage
          }, card);
        });
      });
    }
  }

  async function submitQuizPayload(payload, cardElement) {
    try {
      const res = await fetch('/api/quiz/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (data.is_correct) {
        cardElement.style.borderColor = "#10b981";
        cardElement.innerHTML += `
          <div style="margin-top:12px; padding:10px; background:#ecfdf5; border-radius:6px; color:#047857; font-weight:600; font-size:13px;">
            ${data.feedback}
          </div>
        `;
        // Render 3 Default Follow-up Chips -> Ends turn immediately
        if (data.default_suggestions) renderFollowupChips(data.default_suggestions);
      } else {
        cardElement.style.borderColor = "#f43f5e";
        renderMisconceptionCard(data.misconception);
        if (data.default_suggestions) renderFollowupChips(data.default_suggestions);
      }
    } catch (err) {
      console.error('Quiz submit error:', err);
    }
  }

  // Tool Render 3: Misconception Detection Card
  function renderMisconceptionCard(misconceptionData) {
    const card = document.createElement('div');
    card.className = 'misconception-card';
    card.innerHTML = `
      <div class="misconception-title"><i class="fa-solid fa-triangle-exclamation"></i> Misconception Detection (Phát hiện điểm nhầm lẫn)</div>
      <p style="font-size:13px; font-weight:600; margin-bottom:8px;">${misconceptionData.misconception_point}</p>
      <div style="font-size:13px; margin-bottom:8px;">${misconceptionData.re_explanation}</div>
      <div style="font-size:13px; color:#451a03; background:#fffbe8; padding:8px; border-radius:6px;">${misconceptionData.new_example}</div>
    `;
    chatMessages.appendChild(card);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    if (misconceptionData.recheck_question) {
      renderQuizCard(misconceptionData.recheck_question);
    }
  }

  // Tool Render 4: Follow-up Suggestion Chips
  function renderFollowupChips(suggestions) {
    if (!suggestions || suggestions.length === 0) return;

    const container = document.createElement('div');
    container.className = 'chips-container';
    container.innerHTML = `
      <div style="width:100%; font-size:11px; color:#64748b; font-weight:700;">💡 GỢI Ý CÂU HỎI ĐÀO SÂU:</div>
      ${suggestions.map(s => `<button class="suggestion-chip">${s}</button>`).join('')}
    `;
    chatMessages.appendChild(container);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    container.querySelectorAll('.suggestion-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        sendMessage(chip.textContent);
      });
    });
  }

  // Listeners
  sendBtn.addEventListener('click', () => sendMessage());
  chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

  // 6. Resizer Handle Logic
  let isResizing = false;
  resizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    document.body.style.cursor = 'col-resize';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    const containerWidth = document.querySelector('.app-container').clientWidth;
    const leftWidth = e.clientX;
    const rightWidth = containerWidth - leftWidth;

    if (leftWidth > 350 && rightWidth > 350) {
      leftPane.style.width = `${leftWidth}px`;
      leftPane.style.flex = 'none';
      rightPane.style.width = `${rightWidth}px`;
    }
  });

  document.addEventListener('mouseup', () => {
    isResizing = false;
    document.body.style.cursor = 'default';
  });

  // 7. Dark/Light Theme Toggle
  themeToggleBtn.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    themeToggleBtn.innerHTML = newTheme === 'dark' ? '<i class="fa-regular fa-sun"></i>' : '<i class="fa-regular fa-moon"></i>';
  });

  // 8. Workflow Diagram Modal
  openWfModalBtn.addEventListener('click', () => wfModal.style.display = 'flex');
  closeWfModalBtn.addEventListener('click', () => wfModal.style.display = 'none');
  wfModal.addEventListener('click', (e) => {
    if (e.target === wfModal) wfModal.style.display = 'none';
  });

  // Initialize
  loadSlides();
});
